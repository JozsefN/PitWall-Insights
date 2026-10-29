"""Strategy orchestration consumes reusable feature calculations and a pure plan search."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from modules.feature_metrics.domain.strategy.models import (
    STRATEGY_VERSION,
    StrategyResponse,
)
from modules.feature_metrics.domain.strategy.engine import strategy_features, response
from modules.feature_metrics.infrastructure.strategy_input import (
    StrategyInputProvider,
    digest,
)
from modules.feature_metrics.infrastructure.db_models import SessionAnalysisCacheRecord
from modules.feature_metrics.application.calculation_guard import (
    _ANALYSIS_GATE,
    AnalysisBusyError,
    AnalysisChangedError,
    acquire_database_lock,
)
from modules.decision_engine.domain.strategy_planner import plan_strategies


def evaluate_strategy(
    data, request, context=None, *, context_id=None, fingerprint="synthetic"
):
    snapshot, values, models, series, pit, events, readiness = strategy_features(
        data, request, context, context_id=context_id, fingerprint=fingerprint
    )
    plans, winner, status, planning = plan_strategies(
        snapshot, request, context, values, pit
    )
    models["planning"] = planning
    return response(
        snapshot,
        request,
        context_id,
        fingerprint,
        values,
        models,
        series,
        events,
        readiness,
        plans,
        winner,
        status,
    )


class StrategyService:
    def __init__(self, db):
        self.db = db
        self.provider = StrategyInputProvider(db)

    def evaluate(self, session_id, user_id, request):
        self.provider.session(session_id)
        self.provider.entries(
            session_id, [request.focus_entry_id, *(request.rival_entry_ids or [])]
        )
        record, context = (
            self.provider.context(
                request.context_id, user_id, session_id, request.as_of_ms
            )
            if request.context_id
            else (None, None)
        )
        if context:
            self.provider.validate_context(session_id, context)
        fingerprint = self.provider.fingerprint(session_id)
        key = digest(
            [
                STRATEGY_VERSION,
                session_id,
                user_id,
                request.model_dump(mode="json"),
                fingerprint,
                record.content_hash if record else None,
            ]
        )
        now = datetime.now(timezone.utc)
        cached = self.db.scalar(
            select(SessionAnalysisCacheRecord).where(
                SessionAnalysisCacheRecord.cache_key == key,
                SessionAnalysisCacheRecord.expires_at > now,
            )
        )
        if cached:
            return StrategyResponse.model_validate(cached.payload).model_copy(
                update={"cache_hit": True}
            )
        if not _ANALYSIS_GATE.acquire(blocking=False):
            raise AnalysisBusyError("Analytics is busy; retry shortly")
        try:
            if not acquire_database_lock(self.db):
                raise AnalysisBusyError("Analytics is busy; retry shortly")
            data = self.provider.load_strategy(session_id, request)
            result = evaluate_strategy(
                data,
                request,
                context,
                context_id=request.context_id,
                fingerprint=fingerprint,
            )
            if self.provider.fingerprint(session_id) != fingerprint:
                raise AnalysisChangedError("Session changed during evaluation; retry")
            self.db.execute(
                delete(SessionAnalysisCacheRecord).where(
                    SessionAnalysisCacheRecord.session_id == session_id,
                    SessionAnalysisCacheRecord.expires_at <= now,
                )
            )
            self.db.execute(
                insert(SessionAnalysisCacheRecord)
                .values(
                    owner_user_id=user_id,
                    cache_key=key,
                    session_id=session_id,
                    version=STRATEGY_VERSION,
                    data_fingerprint=fingerprint,
                    created_at=now,
                    expires_at=now + timedelta(hours=1),
                    payload=result.model_dump(mode="json"),
                )
                .on_conflict_do_nothing(
                    index_elements=[SessionAnalysisCacheRecord.cache_key]
                )
            )
            obsolete = (
                select(SessionAnalysisCacheRecord.cache_key)
                .where(
                    SessionAnalysisCacheRecord.session_id == session_id,
                    SessionAnalysisCacheRecord.version == STRATEGY_VERSION,
                )
                .order_by(SessionAnalysisCacheRecord.created_at.desc())
                .offset(32)
            )
            self.db.execute(
                delete(SessionAnalysisCacheRecord).where(
                    SessionAnalysisCacheRecord.cache_key.in_(obsolete)
                )
            )
            self.db.commit()
            return result
        finally:
            self.db.rollback()
            _ANALYSIS_GATE.release()
