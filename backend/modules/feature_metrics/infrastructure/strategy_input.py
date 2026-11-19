from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4
from sqlalchemy import select
from modules.feature_metrics.infrastructure.analysis_input import AnalysisInputProvider
from modules.feature_metrics.infrastructure.db_models import StrategyContextRecord
from modules.feature_metrics.domain.analysis.models import AnalysisRequest
from modules.feature_metrics.domain.analysis.catalog import DEFINITIONS
from modules.feature_metrics.domain.strategy.models import StrategyContext
from modules.session_domain.infrastructure.db_models import (
    EntryLapRecord,
    WeekendRecord,
    SessionStatusEventRecord,
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class StrategyInputProvider(AnalysisInputProvider):
    def load_strategy(self, session_id, request):
        session = self.session(session_id)
        self.entries(
            session_id, [request.focus_entry_id, *(request.rival_entry_ids or [])]
        )
        analysis = AnalysisRequest(
            start_time_ms=max(0, request.as_of_ms - request.telemetry_lookback_ms),
            end_time_ms=request.as_of_ms + 1,
            sample_interval_ms=request.sample_interval_ms,
        )
        data = self.load(
            session_id,
            analysis,
            required_inputs={
                "car",
                "position",
                "laps",
                "reference_line",
                "weather",
                "track_status",
                "race_control",
            },
            as_of_ms=request.as_of_ms,
        )
        data.coverage.update(
            session_phase=self.db.scalar(
                select(SessionStatusEventRecord.status)
                .where(
                    SessionStatusEventRecord.session_id == session_id,
                    SessionStatusEventRecord.session_time_ms <= request.as_of_ms,
                )
                .order_by(SessionStatusEventRecord.session_time_ms.desc())
                .limit(1)
            ),
            race_start_utc=(
                session.scheduled_start_utc.isoformat()
                if session.scheduled_start_utc
                else None
            ),
            coordinate_frame=f"{session.data_provider or session.source}:{session_id}:xy_metres",
            season_year=self.db.scalar(
                select(WeekendRecord.season_year).where(
                    WeekendRecord.id == session.weekend_id
                )
            ),
        )
        return data

    def context(self, context_id, user_id, session_id, cutoff=None):
        record = self.db.scalar(
            select(StrategyContextRecord).where(
                StrategyContextRecord.id == context_id,
                StrategyContextRecord.owner_user_id == user_id,
                StrategyContextRecord.session_id == session_id,
            )
        )
        if record is None:
            raise LookupError("Strategy context not found")
        if cutoff is not None and record.known_at_ms > cutoff:
            raise ValueError("Context was not known at decision time")
        return record, StrategyContext.model_validate(record.payload)

    def source_context(self, session_id, cutoff, context=None):
        """Use native historical pit reports without requiring a manual research import."""
        from modules.feature_metrics.infrastructure.openf1_context import normalize_pit_reports
        session = self.session(session_id)
        details = session.source_details or {}
        rows = details.get("pit_stops") or []
        if not rows or not session.session_time_origin_utc:
            return context
        by_car = {entry.car_number: entry.id for entry in self.entries(session_id)}
        reports = []
        for row in rows:
            try:
                normalized = normalize_pit_reports([row], entries_by_car=by_car,
                    clock_origin=session.session_time_origin_utc, session_key=int(session.session_key))
                reports.extend(v for v in normalized if v.known_at_ms <= cutoff)
            except (ValueError, KeyError, TypeError):
                continue  # A malformed optional source report cannot invalidate all strategy inputs.
        if not reports:
            return context
        if context:
            explicit = {(v.entry_id, v.lap_number) for v in context.pit_observations}
            return context.model_copy(update={"pit_observations": [*context.pit_observations, *(v for v in reports if (v.entry_id,v.lap_number) not in explicit)]})
        return StrategyContext(known_at_ms=max(v.known_at_ms for v in reports),
            source_note="Native OpenF1 pit reports; conservative publication margin, not an original-arrival reconstruction",
            pit_observations=reports)

    def validate_context(self, session_id, context):
        session = self.session(session_id)
        all_ids = {entry.id for entry in self.entries(session_id)}
        if (
            set(context.tyre_inventory) - all_ids
            or {row.entry_id for row in context.pit_observations} - all_ids
        ):
            raise ValueError("Context contains entries from another session")
        year = self.db.scalar(
            select(WeekendRecord.season_year).where(
                WeekendRecord.id == session.weekend_id
            )
        )
        if context.rules and context.rules.season_year != year:
            raise ValueError("Rule profile season does not match session")
        if context.track:
            if (
                not context.track.valid_season_from
                <= year
                <= context.track.valid_season_to
            ):
                raise ValueError("Track geometry is not valid for this season")
            if context.track.coordinate_frame != f"fastf1:{session_id}:xy_metres":
                raise ValueError(
                    "Track geometry coordinate frame must match this session's metre frame"
                )
        payload = context.model_dump(mode="json")
        if len(json.dumps(payload)) > 4_000_000:
            raise ValueError("Strategy context exceeds four megabytes")
        return payload

    def save_context(self, session_id, user_id, context):
        payload = self.validate_context(session_id, context)
        record = StrategyContextRecord(
            id=str(uuid4()),
            session_id=session_id,
            owner_user_id=user_id,
            known_at_ms=context.known_at_ms,
            content_hash=digest(payload),
            created_at=datetime.now(timezone.utc),
            payload=payload,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
