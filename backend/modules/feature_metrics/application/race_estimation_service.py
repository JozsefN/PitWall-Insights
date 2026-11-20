"""One bounded model snapshot shared by every insight panel. No source downloads."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert

from modules.feature_metrics.domain.analysis.models import AnalysisRequest
from modules.feature_metrics.domain.race_estimation.models import (
    MODEL_VERSION,
    ModelAssumptions,
    RaceContext,
    RaceEstimateResponse,
)
from modules.feature_metrics.domain.source_clock import timed_rows
from modules.feature_metrics.domain.snapshot import causal_snapshot
from modules.feature_metrics.domain.race_estimation.engine import estimate_race, visible_context
from modules.feature_metrics.domain.race_estimation.common import phase_at
from modules.feature_metrics.domain.race_estimation.events import reported_events
from modules.feature_metrics.domain.race_estimation.catalog import DEFINITIONS
from modules.feature_metrics.infrastructure.analysis_input import AnalysisInputProvider
from modules.feature_metrics.infrastructure.db_models import SessionAnalysisCacheRecord
from .calculation_guard import (
    _ANALYSIS_GATE,
    AnalysisBusyError,
    AnalysisChangedError,
    acquire_database_lock,
)


class RaceEstimationService:
    def __init__(self, db):
        self.db = db
        self.provider = AnalysisInputProvider(db)

    def reports(self, session_id, request):
        session = self.provider.session(session_id)
        self.provider.entries(session_id, request.entry_ids)
        request = request.model_copy(update={"assumptions": ModelAssumptions()})
        start = max(0, request.as_of_ms - request.lookback_ms)
        data = self.provider.load(
            session_id, AnalysisRequest(start_time_ms=start, end_time_ms=request.as_of_ms + 1),
            required_inputs={"laps", "race_control", "track_status"}, as_of_ms=request.as_of_ms,
        )
        data = causal_snapshot(data, request.as_of_ms, request.lookback_ms)
        context = RaceContext(
            driver_ids={entry.car_number: entry.id for entry in data.entries},
            pits=self._rows((session.source_details or {}).get("pit_stops", []), session),
        )
        context = visible_context(context, request.as_of_ms, request.assumptions.source_report_delay_ms)
        events = sorted(reported_events(data, context, request), key=lambda item: (item.time_ms, item.id), reverse=True)
        return RaceEstimateResponse(
            session_id=session_id, as_of_ms=request.as_of_ms, start_ms=start,
            fingerprint="", assumptions={}, drivers=[], pairs=[],
            conditions={"track_status": phase_at(data.track_status, request.as_of_ms)},
            events=events[:request.max_events], event_count=len(events),
            events_truncated=len(events) > request.max_events, warnings=[],
            interpretation="Published race-control and pit reports, plus recorded best laps.",
        )

    def compute(self, session_id, request):
        session = self.provider.session(session_id)
        self.provider.entries(session_id, request.entry_ids)
        fingerprint = self.provider.fingerprint(session_id)
        owner = self.db.info.get("actor_user_id")
        key = hashlib.sha256(
            json.dumps(
                [
                    session_id,
                    owner,
                    MODEL_VERSION,
                    DEFINITIONS,
                    fingerprint,
                    request.model_dump(mode="json"),
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        now = datetime.now(timezone.utc)
        cached = self.db.scalar(
            select(SessionAnalysisCacheRecord).where(
                SessionAnalysisCacheRecord.cache_key == key,
                SessionAnalysisCacheRecord.expires_at > now,
            )
        )
        if cached:
            return RaceEstimateResponse.model_validate(cached.payload).model_copy(
                update={"cache_hit": True}
            )
        if not _ANALYSIS_GATE.acquire(blocking=False):
            raise AnalysisBusyError("An analysis is running; retry shortly")
        try:
            if not acquire_database_lock(self.db):
                raise AnalysisBusyError("An analysis is running; retry shortly")
            # All roster timing can establish session bests and nearby cars. Only already
            # materialized telemetry is read; selected drivers are filtered in the response.
            analysis_request = AnalysisRequest(
                start_time_ms=max(0, request.as_of_ms - request.lookback_ms),
                end_time_ms=request.as_of_ms + 1,
                sample_interval_ms=request.sample_interval_ms,
            )
            data = self.provider.load(
                session_id,
                analysis_request,
                required_inputs={
                    "car",
                    "position",
                    "laps",
                    "weather",
                    "track_status",
                    "race_control",
                    "reference_line",
                },
                as_of_ms=request.as_of_ms,
            )
            entries = self.provider.entries(session_id)
            details = session.source_details or {}
            context = RaceContext(
                driver_ids={row.car_number: row.id for row in entries},
                intervals=self._rows(details.get("intervals", []), session),
                positions=self._rows(details.get("race_positions", []), session),
                pits=self._rows(details.get("pit_stops", []), session),
                overtakes=self._rows(details.get("overtakes", []), session),
            )
            response = estimate_race(data, context, request, fingerprint)
            if details.get("unavailable_sources"):
                response.warnings.append(
                    "Unavailable source reports: "
                    + ", ".join(details["unavailable_sources"])
                )
            if self.provider.fingerprint(session_id) != fingerprint:
                raise AnalysisChangedError(
                    "Telemetry changed during estimation; retry after materialization completes"
                )
            self.db.execute(
                delete(SessionAnalysisCacheRecord).where(
                    SessionAnalysisCacheRecord.session_id == session_id,
                    SessionAnalysisCacheRecord.version == MODEL_VERSION,
                    SessionAnalysisCacheRecord.owner_user_id == owner,
                    SessionAnalysisCacheRecord.expires_at <= now,
                )
            )
            self.db.execute(
                insert(SessionAnalysisCacheRecord)
                .values(
                    cache_key=key,
                    owner_user_id=owner,
                    session_id=session_id,
                    version=MODEL_VERSION,
                    data_fingerprint=fingerprint,
                    created_at=now,
                    expires_at=now + timedelta(hours=6),
                    payload=response.model_dump(mode="json"),
                )
                .on_conflict_do_nothing(
                    index_elements=[SessionAnalysisCacheRecord.cache_key]
                )
            )
            obsolete = (
                select(SessionAnalysisCacheRecord.cache_key)
                .where(
                    SessionAnalysisCacheRecord.session_id == session_id,
                    SessionAnalysisCacheRecord.version == MODEL_VERSION,
                    SessionAnalysisCacheRecord.owner_user_id == owner,
                )
                .order_by(
                    SessionAnalysisCacheRecord.created_at.desc(),
                    SessionAnalysisCacheRecord.cache_key,
                )
                .offset(32)
            )
            self.db.execute(
                delete(SessionAnalysisCacheRecord).where(
                    SessionAnalysisCacheRecord.cache_key.in_(obsolete)
                )
            )
            self.db.commit()
            return response
        finally:
            self.db.rollback()
            _ANALYSIS_GATE.release()

    @staticmethod
    def _rows(rows, session):
        return timed_rows(rows, session.session_time_origin_utc)
