"""Optional, bounded analytics with persisted, source-versioned results."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete, func
from sqlalchemy.dialects.postgresql import insert
from modules.feature_metrics.domain.analysis.models import (
    ANALYSIS_VERSION,
    AnalysisResponse,
)
from modules.feature_metrics.domain.analysis.catalog import selected_definitions
from modules.feature_metrics.domain.analysis.engine import analyze
from modules.feature_metrics.infrastructure.analysis_input import AnalysisInputProvider
from modules.feature_metrics.infrastructure.db_models import SessionAnalysisCacheRecord

from .calculation_guard import (
    _ANALYSIS_GATE,
    AnalysisBusyError,
    AnalysisChangedError,
    acquire_database_lock,
)

MAX_CACHE_VARIANTS = 32


class SessionAnalysisService:
    def __init__(self, db):
        self.db = db
        self.provider = AnalysisInputProvider(db)

    def compute(self, session_id, request):
        definitions = selected_definitions(request)
        self.provider.session(session_id)
        self.provider.entries(session_id, request.entry_ids)
        fingerprint = self.provider.fingerprint(session_id)
        key = hashlib.sha256(
            json.dumps(
                [
                    session_id,
                    ANALYSIS_VERSION,
                    fingerprint,
                    request.model_dump(mode="json"),
                ],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        now = datetime.now(timezone.utc)
        cached = self.db.scalar(
            select(SessionAnalysisCacheRecord).where(
                SessionAnalysisCacheRecord.cache_key == key,
                SessionAnalysisCacheRecord.expires_at > now,
            )
        )
        if cached is not None:
            return AnalysisResponse.model_validate(cached.payload).model_copy(
                update={"cache_hit": True}
            )
        if not _ANALYSIS_GATE.acquire(blocking=False):
            raise AnalysisBusyError("An analysis is running; retry shortly")
        try:
            # One expensive calculation across API processes; cache hits remain available.
            locked = acquire_database_lock(self.db)
            if not locked:
                raise AnalysisBusyError("An analysis is running; retry shortly")
            data = self.provider.load(session_id, request, definitions)
            response = analyze(data, request, fingerprint)
            if self.provider.fingerprint(session_id) != fingerprint:
                raise AnalysisChangedError(
                    "Telemetry changed during analysis; retry against the completed materialization"
                )
            self.db.execute(
                delete(SessionAnalysisCacheRecord).where(
                    SessionAnalysisCacheRecord.session_id == session_id,
                    SessionAnalysisCacheRecord.expires_at <= now,
                )
            )
            self.db.execute(
                insert(SessionAnalysisCacheRecord)
                .values(
                    cache_key=key,
                    session_id=session_id,
                    version=ANALYSIS_VERSION,
                    data_fingerprint=fingerprint,
                    created_at=now,
                    expires_at=now + timedelta(hours=24),
                    payload=response.model_dump(mode="json"),
                )
                .on_conflict_do_nothing(
                    index_elements=[SessionAnalysisCacheRecord.cache_key]
                )
            )
            obsolete = (
                select(SessionAnalysisCacheRecord.cache_key)
                .where(SessionAnalysisCacheRecord.session_id == session_id)
                .order_by(
                    SessionAnalysisCacheRecord.created_at.desc(),
                    SessionAnalysisCacheRecord.cache_key,
                )
                .offset(MAX_CACHE_VARIANTS)
            )
            self.db.execute(
                delete(SessionAnalysisCacheRecord).where(
                    SessionAnalysisCacheRecord.cache_key.in_(obsolete)
                )
            )
            self.db.commit()
            return response
        finally:
            # Release both the cross-process transaction lock and the local gate on failure.
            self.db.rollback()
            _ANALYSIS_GATE.release()
