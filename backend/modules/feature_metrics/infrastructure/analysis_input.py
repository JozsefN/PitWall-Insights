"""Bounded column queries; analytics never requests source downloads."""

import hashlib
import json
import numpy as np
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from modules.session_domain.infrastructure.db_models import (
    EventSessionRecord,
    WeekendRecord,
    SessionEntryRecord,
    EntryLapRecord,
    EntryStintRecord,
    CarTelemetrySampleRecord,
    PositionSampleRecord,
    SessionWeatherSampleRecord,
    SessionTrackStatusEventRecord,
    SessionRaceControlMessageRecord,
    SessionTickRecord,
)
from modules.telemetry_materialization.infrastructure.db_models import (
    TelemetryCacheSegmentRecord,
)
from modules.feature_metrics.domain.analysis.models import (
    AnalysisData,
    EntryData,
    AnalysisLimitError,
)
from modules.feature_metrics.domain.analysis.geometry import ReferenceLine

MAX_SAMPLES = 1_000_000


class AnalysisInputProvider:
    def __init__(self, db: Session):
        self.db = db

    def session(self, session_id):
        record = self.db.get(EventSessionRecord, session_id)
        if record is None or record.deleted_at is not None:
            raise LookupError("Session not found")
        return record

    def fingerprint(self, session_id):
        # imported_at changes on metadata/full refresh; segments change atomically with worker writes.
        imported = self.db.scalar(
            select(EventSessionRecord.imported_at).where(
                EventSessionRecord.id == session_id
            )
        )
        segments = self.db.execute(
            select(
                TelemetryCacheSegmentRecord.id,
                TelemetryCacheSegmentRecord.status,
                TelemetryCacheSegmentRecord.updated_at,
                TelemetryCacheSegmentRecord.row_count,
            )
            .where(TelemetryCacheSegmentRecord.session_id == session_id)
            .order_by(TelemetryCacheSegmentRecord.id)
        ).all()
        return hashlib.sha256(
            json.dumps(
                [str(imported), [list(map(str, row)) for row in segments]],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def entries(self, session_id, ids=None):
        statement = (
            select(SessionEntryRecord)
            .where(SessionEntryRecord.session_id == session_id)
            .order_by(SessionEntryRecord.car_number)
        )
        records = list(self.db.scalars(statement).all())
        if ids is not None and set(ids) - {row.id for row in records}:
            raise ValueError("Every entry_id must belong to this session")
        records = [row for row in records if ids is None or row.id in ids]
        if len(records) > 64:
            raise AnalysisLimitError("Select at most 64 entries")
        return records

    def rows(self, model, *conditions, order=None):
        statement = select(model.__table__).where(*conditions)
        if order is not None:
            statement = statement.order_by(order)
        return [dict(row) for row in self.db.execute(statement).mappings()]

    def load(
        self,
        session_id,
        request,
        definitions=(),
        *,
        required_inputs=None,
        as_of_ms=None,
    ):
        session = self.session(session_id)
        records = self.entries(session_id, request.entry_ids)
        ids = [record.id for record in records]
        inputs = (
            set(required_inputs)
            if required_inputs is not None
            else {
                item
                for definition in definitions
                for item in definition.required_inputs
            }
        )
        lap_visibility = (
            [EntryLapRecord.lap_start_time_ms <= as_of_ms]
            if as_of_ms is not None
            else []
        )
        laps = self.rows(
            EntryLapRecord,
            EntryLapRecord.session_entry_id.in_(ids),
            *lap_visibility,
            order=EntryLapRecord.lap_number,
        )
        selected = [
            lap
            for lap in laps
            if (request.lap_from is None or lap["lap_number"] >= request.lap_from)
            and (request.lap_to is None or lap["lap_number"] <= request.lap_to)
        ]
        starts = [
            lap["lap_start_time_ms"]
            for lap in selected
            if lap["lap_start_time_ms"] is not None
        ]
        ends = [
            lap["lap_end_time_ms"]
            for lap in selected
            if lap["lap_end_time_ms"] is not None
        ]
        if not starts or not ends:
            bounds = self.db.execute(
                select(
                    func.min(SessionTickRecord.session_time_ms),
                    func.max(SessionTickRecord.session_time_ms),
                ).where(SessionTickRecord.session_id == session_id)
            ).one()
            starts = starts or [bounds[0] or 0]
            ends = ends or [bounds[1] or max(starts) + 1]
        start = (
            request.start_time_ms if request.start_time_ms is not None else min(starts)
        )
        end = request.end_time_ms if request.end_time_ms is not None else max(ends)
        if request.lap_from is not None or request.lap_to is not None:
            if not selected:
                raise ValueError("No laps match the selected lap range")
            start = max(start, min(starts))
            end = min(end, max(ends))
        if start >= end:
            raise ValueError("The selected time/lap window is empty")
        if end - start > 12 * 60 * 60 * 1000:
            raise AnalysisLimitError("Analyze at most 12 hours per request")
        data = AnalysisData(session_id, start, end, source=session.source)
        data.entries = [
            EntryData(row.id, row.car_number, grid_position=row.grid_position)
            for row in records
        ]
        by_id = {entry.id: entry for entry in data.entries}
        for lap in laps:
            by_id[lap["session_entry_id"]].laps.append(lap)
        if "stints" in inputs:
            for stint in self.rows(
                EntryStintRecord, EntryStintRecord.session_entry_id.in_(ids)
            ):
                by_id[stint["session_entry_id"]].stints.append(stint)
        total = 0
        modern = (
            session.source == "fastf1"
            and self.db.scalar(
                select(WeekendRecord.season_year).where(
                    WeekendRecord.id == session.weekend_id
                )
            )
            >= 2020
        )
        for kind, model, attribute in (
            ("car", CarTelemetrySampleRecord, "car"),
            ("position", PositionSampleRecord, "positions"),
        ):
            if kind not in inputs or (kind == "position" and not modern):
                continue
            bucket = func.floor(model.session_time_ms / request.sample_interval_ms)
            statement = select(model.__table__).where(
                model.session_entry_id.in_(ids),
                model.session_time_ms >= start,
                model.session_time_ms < end,
            )
            if request.lap_from is not None or request.lap_to is not None:
                statement = statement.where(
                    model.lap_id.in_([lap["id"] for lap in selected])
                )
            sampled = (
                statement.distinct(model.session_entry_id, bucket)
                .order_by(model.session_entry_id, bucket, model.session_time_ms)
                .subquery()
            )
            query = (
                select(sampled)
                .order_by(sampled.c.session_entry_id, sampled.c.session_time_ms)
                .limit(MAX_SAMPLES - total + 1)
            )
            rows = [dict(row) for row in self.db.execute(query).mappings()]
            total += len(rows)
            if total > MAX_SAMPLES:
                raise AnalysisLimitError(
                    "Analysis exceeds 1,000,000 sampled records; increase sample_interval_ms, shorten the window, or select fewer entries"
                )
            for row in rows:
                getattr(by_id[row["session_entry_id"]], attribute).append(row)
        if "weather" in inputs:
            data.weather = self.rows(
                SessionWeatherSampleRecord,
                SessionWeatherSampleRecord.session_id == session_id,
                SessionWeatherSampleRecord.session_time_ms <= end,
                SessionWeatherSampleRecord.session_time_ms >= max(0, start - 180000),
                order=SessionWeatherSampleRecord.session_time_ms,
            )
        if "track_status" in inputs:
            data.track_status = self.rows(
                SessionTrackStatusEventRecord,
                SessionTrackStatusEventRecord.session_id == session_id,
                SessionTrackStatusEventRecord.session_time_ms <= end,
                order=SessionTrackStatusEventRecord.session_time_ms,
            )
        if "race_control" in inputs:
            data.race_control = self.rows(
                SessionRaceControlMessageRecord,
                SessionRaceControlMessageRecord.session_id == session_id,
                SessionRaceControlMessageRecord.session_time_ms >= start,
                SessionRaceControlMessageRecord.session_time_ms <= end,
                order=SessionRaceControlMessageRecord.session_time_ms,
            )
        if "reference_line" in inputs and modern:
            data.reference = self.reference(
                session_id, end if as_of_ms is None else as_of_ms
            )
        data.coverage = {
            "selected_entries": len(records),
            "sampled_car_records": sum(len(entry.car) for entry in data.entries),
            "sampled_position_records": sum(
                len(entry.positions) for entry in data.entries
            ),
            "weather_records": len(data.weather),
            "track_status_records": len(data.track_status),
            "race_control_records": len(data.race_control),
            "loaded_inputs": sorted(inputs),
            "position_units_supported": modern,
            "max_sample_gap_ms": request.options.max_sample_gap_ms,
            "reference_lap_id": (
                data.reference.lap_id if data.reference is not None else None
            ),
        }
        return data

    def reference(self, session_id, before_ms):
        # Reference from an already completed clean lap: no future replay information.
        lap = EntryLapRecord
        pos = PositionSampleRecord
        candidates = self.db.execute(
            select(
                lap.id, lap.session_entry_id, lap.lap_start_time_ms, lap.lap_end_time_ms
            )
            .join(SessionEntryRecord, SessionEntryRecord.id == lap.session_entry_id)
            .where(
                SessionEntryRecord.session_id == session_id,
                lap.is_accurate.is_(True),
                lap.is_deleted.is_(False),
                lap.is_generated.is_(False),
                lap.pit_in_time_ms.is_(None),
                lap.pit_out_time_ms.is_(None),
                lap.lap_end_time_ms <= before_ms,
                lap.track_status.in_(["1", ""]),
                select(pos.id).where(pos.lap_id == lap.id).exists(),
            )
            .order_by(lap.lap_end_time_ms)
            .limit(5)
        ).all()
        for lap_id, entry_id, lap_start, lap_end in candidates:
            points = self.db.execute(
                select(pos.x, pos.y, pos.session_time_ms)
                .where(pos.lap_id == lap_id)
                .order_by(pos.session_time_ms)
                .limit(2500)
            ).all()
            if len(points) < 20:
                continue
            try:
                return ReferenceLine(
                    np.asarray(points, dtype=float)[:, :2] * 0.1,
                    lap_id=lap_id,
                    entry_id=entry_id,
                    sample_times_ms=(
                        np.asarray(points, dtype=float)[:, 2] - lap_start
                        if lap_start is not None
                        else None
                    ),
                    lap_duration_ms=(
                        lap_end - lap_start if lap_start is not None else None
                    ),
                )
            except ValueError:
                continue
        return None
