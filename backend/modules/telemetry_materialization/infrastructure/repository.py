from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, joinedload

from modules.normalization.domain.models import (
    CarTelemetrySamplePayload,
    PositionSamplePayload,
    SessionSnapshot,
)
from modules.session_domain.domain.models import SessionImportRequest
from modules.session_domain.infrastructure.models import (
    CarTelemetrySampleRecord,
    EntryLapRecord,
    EntryStintRecord,
    EventSessionRecord,
    PositionSampleRecord,
    SessionEntryRecord,
    SessionTickRecord,
)
from modules.session_domain.infrastructure.models.common import generate_uuid
from modules.telemetry_materialization.domain.models import (
    TelemetryMaterializationEnsureResponse,
    TelemetryMaterializationJobRead,
    TelemetryMaterializationRequest,
    TelemetrySegmentRead,
)
from modules.telemetry_materialization.infrastructure.db_models import (
    TelemetryCacheSegmentRecord,
    TelemetryMaterializationJobRecord,
)

BULK_INSERT_CHUNK_SIZE = 5000


class TelemetryMaterializationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_materialization(
        self,
        request: TelemetryMaterializationRequest,
        *,
        expires_at: datetime,
    ) -> TelemetryMaterializationEnsureResponse:
        self._assert_session_exists(request.session_id)
        self._assert_entries_belong_to_session(request.session_id, request.entry_ids)

        if not request.force_refresh:
            self._backfill_completed_segments_from_existing_rows(request, expires_at=expires_at)

        ready_segments: list[TelemetrySegmentRead] = []
        missing_pairs: list[tuple[str, str]] = []
        for entry_id in request.entry_ids:
            for kind in request.kinds:
                segment = self._find_satisfying_segment(
                    session_id=request.session_id,
                    entry_id=entry_id,
                    kind=kind,
                    scope=request.scope,
                    lap_number=request.lap_number,
                )
                if segment is None or request.force_refresh:
                    missing_pairs.append((entry_id, kind))
                else:
                    ready_segments.append(self.to_segment_model(segment))

        if not missing_pairs:
            return TelemetryMaterializationEnsureResponse(ready=True, segments=ready_segments)

        active_job = None if request.force_refresh else self._find_active_job_covering_pairs(request, missing_pairs)
        if active_job is not None:
            self._cancel_queued_jobs_covered_by_record(active_job)
            return TelemetryMaterializationEnsureResponse(
                ready=False,
                job_id=active_job.id,
                segments=self.list_segments_for_request(request),
            )

        job = self.create_job(request, expires_at=expires_at)
        self.queue_segments(
            request.session_id,
            missing_pairs,
            scope=request.scope,
            lap_number=request.lap_number,
            expires_at=expires_at,
            force_refresh=request.force_refresh,
        )
        self._cancel_queued_jobs_covered_by_request(request, keep_job_id=job.id)
        return TelemetryMaterializationEnsureResponse(
            ready=False,
            job_id=job.id,
            segments=self.list_segments_for_request(request),
        )

    def create_job(
        self,
        request: TelemetryMaterializationRequest,
        *,
        expires_at: datetime,
    ) -> TelemetryMaterializationJobRead:
        record = TelemetryMaterializationJobRecord(
            session_id=request.session_id,
            entry_ids=request.entry_ids,
            kinds=request.kinds,
            scope=request.scope,
            lap_number=self._lap_value(request.scope, request.lap_number),
            force_refresh=request.force_refresh,
            expires_at=expires_at,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self.to_job_model(record)

    def queue_segments(
        self,
        session_id: str,
        pairs: list[tuple[str, str]],
        *,
        scope: str,
        lap_number: int | None,
        expires_at: datetime,
        force_refresh: bool,
    ) -> None:
        lap_value = self._lap_value(scope, lap_number)
        for entry_id, kind in pairs:
            segment = self._get_exact_segment(
                session_id=session_id,
                entry_id=entry_id,
                kind=kind,
                scope=scope,
                lap_number=lap_number,
            )
            if segment is None:
                segment = TelemetryCacheSegmentRecord(
                    session_id=session_id,
                    session_entry_id=entry_id,
                    kind=kind,
                    scope=scope,
                    lap_number=lap_value,
                    expires_at=expires_at,
                )
            segment.status = "queued"
            segment.error_message = None
            segment.expires_at = expires_at
            if force_refresh:
                segment.row_count = 0
            self.db.add(segment)
        self.db.commit()

    def get_job(self, job_id: str) -> TelemetryMaterializationJobRead | None:
        record = self.db.get(TelemetryMaterializationJobRecord, job_id)
        return self.to_job_model(record) if record is not None else None

    def list_jobs(self, *, limit: int = 50) -> list[TelemetryMaterializationJobRead]:
        records = (
            self.db.query(TelemetryMaterializationJobRecord)
            .order_by(TelemetryMaterializationJobRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self.to_job_model(record) for record in records]

    def claim_next_job(self, *, now: datetime) -> TelemetryMaterializationJobRecord | None:
        records = (
            self.db.query(TelemetryMaterializationJobRecord)
            .filter(TelemetryMaterializationJobRecord.status == "queued")
            .order_by(TelemetryMaterializationJobRecord.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(50)
            .all()
        )
        if not records:
            return None

        record = max(
            records,
            key=lambda candidate: (
                len(candidate.entry_ids) * len(candidate.kinds),
                candidate.created_at,
            ),
        )
        self._cancel_queued_jobs_covered_by_record(record, now=now, commit=False)
        record.status = "running"
        record.progress_stage = "loading_source"
        record.attempt_count += 1
        record.started_at = record.started_at or now
        record.heartbeat_at = now
        record.error_message = None
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def mark_stage(self, job_id: str, *, stage: str, now: datetime) -> TelemetryMaterializationJobRead | None:
        record = self.db.get(TelemetryMaterializationJobRecord, job_id)
        if record is None:
            return None
        record.progress_stage = stage
        record.heartbeat_at = now
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self.to_job_model(record)

    def touch_heartbeat(self, job_id: str, *, now: datetime) -> None:
        record = self.db.get(TelemetryMaterializationJobRecord, job_id)
        if record is None:
            return
        record.heartbeat_at = now
        self.db.add(record)
        self.db.commit()

    def mark_completed(
        self,
        job_id: str,
        *,
        source_version: str | None,
        rows_written: int,
        now: datetime,
    ) -> TelemetryMaterializationJobRead | None:
        record = self.db.get(TelemetryMaterializationJobRecord, job_id)
        if record is None:
            return None
        record.status = "completed"
        record.progress_stage = "completed"
        record.source_version = source_version
        record.rows_written = rows_written
        record.heartbeat_at = now
        record.finished_at = now
        record.error_message = None
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self.to_job_model(record)

    def mark_failed(self, job_id: str, *, error_message: str, now: datetime) -> TelemetryMaterializationJobRead | None:
        record = self.db.get(TelemetryMaterializationJobRecord, job_id)
        if record is None:
            return None
        record.status = "failed"
        record.progress_stage = "failed"
        record.heartbeat_at = now
        record.finished_at = now
        record.error_message = error_message
        self.db.add(record)
        self._mark_job_segments_failed(record, error_message=error_message, now=now)
        self.db.commit()
        self.db.refresh(record)
        return self.to_job_model(record)

    def recover_stale_running_jobs(
        self,
        *,
        stale_before: datetime,
        now: datetime,
        max_attempts: int,
    ) -> int:
        records = (
            self.db.query(TelemetryMaterializationJobRecord)
            .filter(
                TelemetryMaterializationJobRecord.status == "running",
                TelemetryMaterializationJobRecord.heartbeat_at < stale_before,
            )
            .all()
        )
        for record in records:
            if record.attempt_count < max_attempts:
                record.status = "queued"
                record.progress_stage = "queued"
                record.heartbeat_at = None
                record.error_message = "Worker heartbeat expired; job was queued for retry."
            else:
                record.status = "failed"
                record.progress_stage = "failed"
                record.heartbeat_at = now
                record.finished_at = now
                record.error_message = "Worker heartbeat expired; retry limit reached."
                self._mark_job_segments_failed(record, error_message=record.error_message, now=now)
            self.db.add(record)

        if records:
            self.db.commit()
        return len(records)

    def build_session_import_request(self, session_id: str) -> tuple[str, SessionImportRequest]:
        record = (
            self.db.query(EventSessionRecord)
            .options(joinedload(EventSessionRecord.weekend))
            .filter(EventSessionRecord.id == session_id)
            .first()
        )
        if record is None:
            raise ValueError("Session not found")

        return record.source, SessionImportRequest(
            season_year=record.weekend.season_year,
            round_number=record.weekend.round_number or 0,
            session_name=record.session_name,
            source_session_key=record.source_session_key,
            import_profile="full",
        )

    def materialize_snapshot(
        self,
        job: TelemetryMaterializationJobRecord,
        snapshot: SessionSnapshot,
        *,
        source_version: str | None,
        heartbeat: Callable[[], None] | None = None,
    ) -> int:
        request = self.to_request(job)
        entry_source_keys = self._entry_source_keys(job.session_id, job.entry_ids)
        selected_source_keys = set(entry_source_keys.values())
        selected_car = [
            payload for payload in snapshot.car_samples
            if "car" in job.kinds and self._payload_matches(payload, selected_source_keys, request)
        ]
        selected_position = [
            payload for payload in snapshot.position_samples
            if "position" in job.kinds and self._payload_matches(payload, selected_source_keys, request)
        ]

        if job.force_refresh:
            self._delete_existing_rows(request)

        tick_id_map = self._ensure_ticks(
            job.session_id,
            [*selected_car, *selected_position],
            heartbeat=heartbeat,
        )
        lap_id_map = self._lap_id_map(job.session_id, job.entry_ids)
        stint_id_map = self._stint_id_map(job.session_id, job.entry_ids)

        rows_written = 0
        if "car" in job.kinds:
            rows_written += self._insert_car_samples(
                selected_car,
                entry_source_keys=entry_source_keys,
                tick_id_map=tick_id_map,
                lap_id_map=lap_id_map,
                stint_id_map=stint_id_map,
                heartbeat=heartbeat,
            )
        if "position" in job.kinds:
            rows_written += self._insert_position_samples(
                selected_position,
                entry_source_keys=entry_source_keys,
                tick_id_map=tick_id_map,
                lap_id_map=lap_id_map,
                stint_id_map=stint_id_map,
                heartbeat=heartbeat,
            )

        self._mark_segments_completed(request, source_version=source_version)
        self._refresh_session_telemetry_status(job.session_id)
        self.db.commit()
        return rows_written

    def list_segments_for_request(
        self,
        request: TelemetryMaterializationRequest,
    ) -> list[TelemetrySegmentRead]:
        records: list[TelemetryCacheSegmentRecord] = []
        for entry_id in request.entry_ids:
            for kind in request.kinds:
                segment = self._find_satisfying_segment(
                    session_id=request.session_id,
                    entry_id=entry_id,
                    kind=kind,
                    scope=request.scope,
                    lap_number=request.lap_number,
                )
                if segment is not None:
                    records.append(segment)
        return [self.to_segment_model(record) for record in records]

    def _find_active_job_covering_pairs(
        self,
        request: TelemetryMaterializationRequest,
        pairs: list[tuple[str, str]],
    ) -> TelemetryMaterializationJobRecord | None:
        required_pairs = set(pairs)
        if not required_pairs:
            return None

        records = (
            self.db.query(TelemetryMaterializationJobRecord)
            .filter(
                TelemetryMaterializationJobRecord.session_id == request.session_id,
                TelemetryMaterializationJobRecord.status.in_(["queued", "running"]),
                TelemetryMaterializationJobRecord.scope == request.scope,
                TelemetryMaterializationJobRecord.lap_number == self._lap_value(request.scope, request.lap_number),
            )
            .order_by(TelemetryMaterializationJobRecord.created_at.asc())
            .all()
        )
        covering_records = []
        for record in records:
            entry_ids = set(record.entry_ids)
            kinds = set(record.kinds)
            if all(entry_id in entry_ids and kind in kinds for entry_id, kind in required_pairs):
                covering_records.append(record)

        if covering_records:
            return max(
                covering_records,
                key=lambda record: (
                    len(record.entry_ids) * len(record.kinds),
                    record.created_at,
                ),
            )

        return None

    def _cancel_queued_jobs_covered_by_record(
        self,
        covering_job: TelemetryMaterializationJobRecord,
        *,
        now: datetime | None = None,
        commit: bool = True,
    ) -> int:
        request = self.to_request(covering_job)
        return self._cancel_queued_jobs_covered_by_request(
            request,
            keep_job_id=covering_job.id,
            now=now,
            commit=commit,
        )

    def _cancel_queued_jobs_covered_by_request(
        self,
        request: TelemetryMaterializationRequest,
        *,
        keep_job_id: str,
        now: datetime | None = None,
        commit: bool = True,
    ) -> int:
        covered_pairs = {
            (entry_id, kind)
            for entry_id in request.entry_ids
            for kind in request.kinds
        }
        if not covered_pairs:
            return 0

        cancelled_at = now or datetime.now(timezone.utc)
        records = (
            self.db.query(TelemetryMaterializationJobRecord)
            .filter(
                TelemetryMaterializationJobRecord.id != keep_job_id,
                TelemetryMaterializationJobRecord.session_id == request.session_id,
                TelemetryMaterializationJobRecord.status == "queued",
                TelemetryMaterializationJobRecord.scope == request.scope,
                TelemetryMaterializationJobRecord.lap_number == self._lap_value(request.scope, request.lap_number),
                TelemetryMaterializationJobRecord.force_refresh.is_(False),
            )
            .all()
        )
        cancelled_count = 0
        for record in records:
            candidate_pairs = {
                (entry_id, kind)
                for entry_id in record.entry_ids
                for kind in record.kinds
            }
            if not candidate_pairs or not candidate_pairs.issubset(covered_pairs):
                continue

            record.status = "cancelled"
            record.progress_stage = "cancelled"
            record.finished_at = cancelled_at
            record.heartbeat_at = cancelled_at
            record.error_message = "Superseded by a broader telemetry materialization job."
            self.db.add(record)
            cancelled_count += 1

        if cancelled_count and commit:
            self.db.commit()
        return cancelled_count

    def _insert_car_samples(
        self,
        payloads: list[CarTelemetrySamplePayload],
        *,
        entry_source_keys: dict[str, str],
        tick_id_map: dict[int, str],
        lap_id_map: dict[tuple[str, int], str],
        stint_id_map: dict[tuple[str, int], str],
        heartbeat: Callable[[], None] | None,
    ) -> int:
        source_to_entry = {source_key: entry_id for entry_id, source_key in entry_source_keys.items()}
        rows = (
            {
                "id": generate_uuid(),
                "session_entry_id": source_to_entry[payload.source_entry_key],
                "tick_id": tick_id_map[payload.session_time_ms],
                "lap_id": lap_id_map.get((source_to_entry[payload.source_entry_key], payload.lap_number)) if payload.lap_number else None,
                "stint_id": stint_id_map.get((source_to_entry[payload.source_entry_key], payload.stint_number)) if payload.stint_number else None,
                "sample_seq": payload.sample_seq,
                "session_time_ms": payload.session_time_ms,
                "source_time_utc": payload.source_time_utc,
                "source": payload.source,
                "speed_kph": payload.speed_kph,
                "rpm": payload.rpm,
                "gear": payload.gear,
                "throttle_pct": payload.throttle_pct,
                "brake_on": payload.brake_on,
                "drs_state": payload.drs_state,
            }
            for payload in payloads
        )
        return self._bulk_insert(
            CarTelemetrySampleRecord,
            rows,
            conflict_constraint="uq_car_telemetry_sample_seq",
            heartbeat=heartbeat,
        )

    def _insert_position_samples(
        self,
        payloads: list[PositionSamplePayload],
        *,
        entry_source_keys: dict[str, str],
        tick_id_map: dict[int, str],
        lap_id_map: dict[tuple[str, int], str],
        stint_id_map: dict[tuple[str, int], str],
        heartbeat: Callable[[], None] | None,
    ) -> int:
        source_to_entry = {source_key: entry_id for entry_id, source_key in entry_source_keys.items()}
        rows = (
            {
                "id": generate_uuid(),
                "session_entry_id": source_to_entry[payload.source_entry_key],
                "tick_id": tick_id_map[payload.session_time_ms],
                "lap_id": lap_id_map.get((source_to_entry[payload.source_entry_key], payload.lap_number)) if payload.lap_number else None,
                "stint_id": stint_id_map.get((source_to_entry[payload.source_entry_key], payload.stint_number)) if payload.stint_number else None,
                "sample_seq": payload.sample_seq,
                "session_time_ms": payload.session_time_ms,
                "source_time_utc": payload.source_time_utc,
                "source": payload.source,
                "x": payload.x,
                "y": payload.y,
                "z": payload.z,
                "track_status": payload.track_status,
            }
            for payload in payloads
        )
        return self._bulk_insert(
            PositionSampleRecord,
            rows,
            conflict_constraint="uq_position_samples_seq",
            heartbeat=heartbeat,
        )

    def _bulk_insert(
        self,
        model: type,
        rows: Iterable[dict],
        *,
        conflict_constraint: str,
        heartbeat: Callable[[], None] | None = None,
    ) -> int:
        total = 0
        batch: list[dict] = []
        for row in rows:
            batch.append(row)
            if len(batch) >= BULK_INSERT_CHUNK_SIZE:
                total += self._execute_insert_batch(model, batch, conflict_constraint=conflict_constraint)
                batch.clear()
                if heartbeat is not None:
                    heartbeat()

        if batch:
            total += self._execute_insert_batch(model, batch, conflict_constraint=conflict_constraint)
            if heartbeat is not None:
                heartbeat()
        return total

    def _execute_insert_batch(self, model: type, batch: list[dict], *, conflict_constraint: str) -> int:
        statement = pg_insert(model.__table__).on_conflict_do_nothing(constraint=conflict_constraint)
        result = self.db.execute(statement, batch)
        return max(int(result.rowcount or 0), 0)

    def _ensure_ticks(
        self,
        session_id: str,
        payloads: list[CarTelemetrySamplePayload | PositionSamplePayload],
        *,
        heartbeat: Callable[[], None] | None,
    ) -> dict[int, str]:
        payload_by_time: dict[int, CarTelemetrySamplePayload | PositionSamplePayload] = {}
        for payload in payloads:
            payload_by_time.setdefault(payload.session_time_ms, payload)

        if not payload_by_time:
            return {}

        existing = (
            self.db.query(SessionTickRecord)
            .filter(
                SessionTickRecord.session_id == session_id,
                SessionTickRecord.session_time_ms.in_(list(payload_by_time.keys())),
            )
            .all()
        )
        tick_id_map = {record.session_time_ms: record.id for record in existing}
        missing_times = sorted(set(payload_by_time) - set(tick_id_map))
        if not missing_times:
            return tick_id_map

        next_tick_no = int(
            self.db.query(func.max(SessionTickRecord.tick_no))
            .filter(SessionTickRecord.session_id == session_id)
            .scalar()
            or 0
        ) + 1
        rows = []
        for offset, session_time_ms in enumerate(missing_times):
            payload = payload_by_time[session_time_ms]
            tick_id = generate_uuid()
            tick_id_map[session_time_ms] = tick_id
            rows.append(
                {
                    "id": tick_id,
                    "session_id": session_id,
                    "tick_no": next_tick_no + offset,
                    "session_time_ms": session_time_ms,
                    "source_time_utc": payload.source_time_utc,
                    "source_kind": "telemetry",
                }
            )
        self._bulk_insert(
            SessionTickRecord,
            rows,
            conflict_constraint="uq_session_ticks_time",
            heartbeat=heartbeat,
        )
        return tick_id_map

    def _delete_existing_rows(self, request: TelemetryMaterializationRequest) -> None:
        for entry_id in request.entry_ids:
            if "car" in request.kinds:
                self._delete_existing_rows_for_kind(CarTelemetrySampleRecord, entry_id, request)
            if "position" in request.kinds:
                self._delete_existing_rows_for_kind(PositionSampleRecord, entry_id, request)

    def _delete_existing_rows_for_kind(
        self,
        model: type,
        entry_id: str,
        request: TelemetryMaterializationRequest,
    ) -> None:
        query = self.db.query(model).filter(model.session_entry_id == entry_id)
        if request.scope == "lap":
            lap_ids = (
                self.db.query(EntryLapRecord.id)
                .filter(
                    EntryLapRecord.session_entry_id == entry_id,
                    EntryLapRecord.lap_number == request.lap_number,
                )
                .subquery()
            )
            query = query.filter(model.lap_id.in_(lap_ids))
        query.delete(synchronize_session=False)

    def _mark_segments_completed(
        self,
        request: TelemetryMaterializationRequest,
        *,
        source_version: str | None,
    ) -> None:
        for entry_id in request.entry_ids:
            for kind in request.kinds:
                segment = self._get_exact_segment(
                    session_id=request.session_id,
                    entry_id=entry_id,
                    kind=kind,
                    scope=request.scope,
                    lap_number=request.lap_number,
                )
                if segment is None:
                    segment = TelemetryCacheSegmentRecord(
                        session_id=request.session_id,
                        session_entry_id=entry_id,
                        kind=kind,
                        scope=request.scope,
                        lap_number=self._lap_value(request.scope, request.lap_number),
                    )
                segment.status = "completed"
                segment.row_count = self._count_rows_for_segment(
                    kind=kind,
                    entry_id=entry_id,
                    scope=request.scope,
                    lap_number=request.lap_number,
                )
                segment.source_version = source_version
                segment.error_message = None
                self.db.add(segment)

    def _mark_job_segments_failed(
        self,
        job: TelemetryMaterializationJobRecord,
        *,
        error_message: str,
        now: datetime,
    ) -> None:
        for entry_id in job.entry_ids:
            for kind in job.kinds:
                segment = self._get_exact_segment(
                    session_id=job.session_id,
                    entry_id=entry_id,
                    kind=kind,
                    scope=job.scope,
                    lap_number=self._model_lap_number(job),
                )
                if segment is not None and segment.status != "completed":
                    segment.status = "failed"
                    segment.error_message = error_message
                    segment.updated_at = now
                    self.db.add(segment)

    def _backfill_completed_segments_from_existing_rows(
        self,
        request: TelemetryMaterializationRequest,
        *,
        expires_at: datetime,
    ) -> None:
        changed = False
        for entry_id in request.entry_ids:
            for kind in request.kinds:
                segment = self._find_satisfying_segment(
                    session_id=request.session_id,
                    entry_id=entry_id,
                    kind=kind,
                    scope=request.scope,
                    lap_number=request.lap_number,
                )
                if segment is not None:
                    continue
                row_count = self._count_rows_for_segment(
                    kind=kind,
                    entry_id=entry_id,
                    scope=request.scope,
                    lap_number=request.lap_number,
                )
                if row_count <= 0:
                    continue
                exact_segment = self._get_exact_segment(
                    session_id=request.session_id,
                    entry_id=entry_id,
                    kind=kind,
                    scope=request.scope,
                    lap_number=request.lap_number,
                )
                if exact_segment is None:
                    exact_segment = TelemetryCacheSegmentRecord(
                        session_id=request.session_id,
                        session_entry_id=entry_id,
                        kind=kind,
                        scope=request.scope,
                        lap_number=self._lap_value(request.scope, request.lap_number),
                    )
                exact_segment.status = "completed"
                exact_segment.row_count = row_count
                exact_segment.error_message = None
                exact_segment.expires_at = expires_at
                self.db.add(exact_segment)
                changed = True
        if changed:
            self.db.commit()

    def _find_satisfying_segment(
        self,
        *,
        session_id: str,
        entry_id: str,
        kind: str,
        scope: str,
        lap_number: int | None,
    ) -> TelemetryCacheSegmentRecord | None:
        exact = self._get_exact_segment(
            session_id=session_id,
            entry_id=entry_id,
            kind=kind,
            scope=scope,
            lap_number=lap_number,
        )
        if exact is not None and exact.status == "completed":
            return exact

        if scope == "lap":
            session_segment = self._get_exact_segment(
                session_id=session_id,
                entry_id=entry_id,
                kind=kind,
                scope="session",
                lap_number=None,
            )
            if session_segment is not None and session_segment.status == "completed":
                return session_segment

        return None

    def _get_exact_segment(
        self,
        *,
        session_id: str,
        entry_id: str,
        kind: str,
        scope: str,
        lap_number: int | None,
    ) -> TelemetryCacheSegmentRecord | None:
        return (
            self.db.query(TelemetryCacheSegmentRecord)
            .filter(
                TelemetryCacheSegmentRecord.session_id == session_id,
                TelemetryCacheSegmentRecord.session_entry_id == entry_id,
                TelemetryCacheSegmentRecord.kind == kind,
                TelemetryCacheSegmentRecord.scope == scope,
                TelemetryCacheSegmentRecord.lap_number == self._lap_value(scope, lap_number),
            )
            .first()
        )

    def _count_rows_for_segment(
        self,
        *,
        kind: str,
        entry_id: str,
        scope: str,
        lap_number: int | None,
    ) -> int:
        model = CarTelemetrySampleRecord if kind == "car" else PositionSampleRecord
        query = self.db.query(func.count(model.id)).filter(model.session_entry_id == entry_id)
        if scope == "lap":
            query = query.join(EntryLapRecord, model.lap_id == EntryLapRecord.id).filter(
                EntryLapRecord.lap_number == lap_number
            )
        return int(query.scalar() or 0)

    def _refresh_session_telemetry_status(self, session_id: str) -> None:
        session = self.db.get(EventSessionRecord, session_id)
        if session is None:
            return

        all_entry_ids = [
            row[0]
            for row in self.db.query(SessionEntryRecord.id)
            .filter(SessionEntryRecord.session_id == session_id)
            .all()
        ]
        if not all_entry_ids:
            return

        any_rows = (
            self.db.query(func.count(CarTelemetrySampleRecord.id))
            .join(SessionEntryRecord, CarTelemetrySampleRecord.session_entry_id == SessionEntryRecord.id)
            .filter(SessionEntryRecord.session_id == session_id)
            .scalar()
            or 0
        ) + (
            self.db.query(func.count(PositionSampleRecord.id))
            .join(SessionEntryRecord, PositionSampleRecord.session_entry_id == SessionEntryRecord.id)
            .filter(SessionEntryRecord.session_id == session_id)
            .scalar()
            or 0
        )
        if any_rows <= 0:
            return

        all_session_segments_loaded = all(
            self._find_satisfying_segment(
                session_id=session_id,
                entry_id=entry_id,
                kind=kind,
                scope="session",
                lap_number=None,
            ) is not None
            for entry_id in all_entry_ids
            for kind in ("car", "position")
        )
        session.telemetry_status = "loaded" if all_session_segments_loaded else "partial"
        if all_session_segments_loaded:
            session.import_profile = "full"
        self.db.add(session)

    def _entry_source_keys(self, session_id: str, entry_ids: list[str]) -> dict[str, str]:
        records = (
            self.db.query(SessionEntryRecord)
            .filter(
                SessionEntryRecord.session_id == session_id,
                SessionEntryRecord.id.in_(entry_ids),
            )
            .all()
        )
        return {record.id: record.source_entry_key for record in records}

    def _lap_id_map(self, session_id: str, entry_ids: list[str]) -> dict[tuple[str, int], str]:
        rows = (
            self.db.query(EntryLapRecord)
            .join(SessionEntryRecord, EntryLapRecord.session_entry_id == SessionEntryRecord.id)
            .filter(
                SessionEntryRecord.session_id == session_id,
                EntryLapRecord.session_entry_id.in_(entry_ids),
            )
            .all()
        )
        return {(row.session_entry_id, row.lap_number): row.id for row in rows}

    def _stint_id_map(self, session_id: str, entry_ids: list[str]) -> dict[tuple[str, int], str]:
        rows = (
            self.db.query(EntryStintRecord)
            .join(SessionEntryRecord, EntryStintRecord.session_entry_id == SessionEntryRecord.id)
            .filter(
                SessionEntryRecord.session_id == session_id,
                EntryStintRecord.session_entry_id.in_(entry_ids),
            )
            .all()
        )
        return {(row.session_entry_id, row.stint_number): row.id for row in rows}

    @staticmethod
    def _payload_matches(
        payload: CarTelemetrySamplePayload | PositionSamplePayload,
        selected_source_keys: set[str],
        request: TelemetryMaterializationRequest,
    ) -> bool:
        if payload.source_entry_key not in selected_source_keys:
            return False
        if request.scope == "lap" and payload.lap_number != request.lap_number:
            return False
        return True

    def _assert_session_exists(self, session_id: str) -> None:
        if self.db.get(EventSessionRecord, session_id) is None:
            raise ValueError("Session not found")

    def _assert_entries_belong_to_session(self, session_id: str, entry_ids: list[str]) -> None:
        count = (
            self.db.query(func.count(SessionEntryRecord.id))
            .filter(
                SessionEntryRecord.session_id == session_id,
                SessionEntryRecord.id.in_(entry_ids),
            )
            .scalar()
            or 0
        )
        if count != len(set(entry_ids)):
            raise ValueError("One or more entries do not belong to this session")

    @staticmethod
    def _lap_value(scope: str, lap_number: int | None) -> int:
        return lap_number if scope == "lap" and lap_number is not None else 0

    @staticmethod
    def _model_lap_number(record: TelemetryMaterializationJobRecord) -> int | None:
        return record.lap_number if record.scope == "lap" and record.lap_number > 0 else None

    @staticmethod
    def to_request(record: TelemetryMaterializationJobRecord) -> TelemetryMaterializationRequest:
        return TelemetryMaterializationRequest(
            session_id=record.session_id,
            entry_ids=record.entry_ids,
            kinds=record.kinds,
            scope=record.scope,
            lap_number=TelemetryMaterializationRepository._model_lap_number(record),
            force_refresh=record.force_refresh,
        )

    @staticmethod
    def to_job_model(record: TelemetryMaterializationJobRecord) -> TelemetryMaterializationJobRead:
        return TelemetryMaterializationJobRead(
            id=record.id,
            session_id=record.session_id,
            entry_ids=list(record.entry_ids),
            kinds=list(record.kinds),
            scope=record.scope,
            lap_number=TelemetryMaterializationRepository._model_lap_number(record),
            status=record.status,
            progress_stage=record.progress_stage,
            attempt_count=record.attempt_count,
            force_refresh=record.force_refresh,
            source_version=record.source_version,
            rows_written=record.rows_written,
            error_message=record.error_message,
            created_at=record.created_at,
            started_at=record.started_at,
            heartbeat_at=record.heartbeat_at,
            finished_at=record.finished_at,
            expires_at=record.expires_at,
        )

    @staticmethod
    def to_segment_model(record: TelemetryCacheSegmentRecord) -> TelemetrySegmentRead:
        return TelemetrySegmentRead(
            id=record.id,
            session_id=record.session_id,
            session_entry_id=record.session_entry_id,
            kind=record.kind,
            scope=record.scope,
            lap_number=record.lap_number if record.scope == "lap" and record.lap_number > 0 else None,
            status=record.status,
            row_count=record.row_count,
            source_version=record.source_version,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
            expires_at=record.expires_at,
        )
