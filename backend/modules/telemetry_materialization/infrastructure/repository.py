from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone, timedelta
from itertools import chain

from sqlalchemy import Column, MetaData, Table, func, select, literal_column, text, or_
from psycopg import sql
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, joinedload

from modules.normalization.domain.models import (
    CarTelemetrySamplePayload,
    PositionSamplePayload,
    SessionSnapshot,
)
from modules.ingestion.domain.models import TelemetrySelection
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
from modules.session_domain.infrastructure.race_control import refresh_race_control
from modules.telemetry_materialization.domain.models import (
    TelemetryMaterializationEnsureResponse,
    TelemetryMaterializationJobRead,
    TelemetryMaterializationRequest,
    TelemetrySegmentRead,
)
from modules.telemetry_materialization.infrastructure.db_models import (
    TelemetryCacheSegmentRecord,
    TelemetryMaterializationJobRecord,
    TelemetryWorkerHeartbeatRecord,
)

BULK_INSERT_CHUNK_SIZE = 5000


class TelemetryMaterializationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _lock_session(self, session_id: str, purpose: str) -> None:
        # Separate queue and write locks: readiness checks remain responsive
        # while another worker persists a large session. Locks end with the txn.
        self.db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                        {"key": f"telemetry:{purpose}:{session_id}"})

    def touch_worker(self, worker_id: str, *, hostname: str, process_id: int, started_at: datetime, now: datetime) -> None:
        statement = pg_insert(TelemetryWorkerHeartbeatRecord).values(
            worker_id=worker_id,hostname=hostname,process_id=process_id,started_at=started_at,heartbeat_at=now,
        ).on_conflict_do_update(index_elements=["worker_id"],set_={"heartbeat_at":now,"started_at":started_at})
        self.db.execute(statement)
        self.db.query(TelemetryWorkerHeartbeatRecord).filter(TelemetryWorkerHeartbeatRecord.heartbeat_at < now-timedelta(days=1)).delete()
        self.db.commit()

    def worker_health(self, *, now: datetime) -> dict:
        fresh_before = now-timedelta(seconds=45)
        workers = self.db.query(func.count(TelemetryWorkerHeartbeatRecord.worker_id)).filter(
            TelemetryWorkerHeartbeatRecord.heartbeat_at >= fresh_before).scalar()
        last_seen = self.db.query(func.max(TelemetryWorkerHeartbeatRecord.heartbeat_at)).scalar()
        counts = dict(self.db.query(TelemetryMaterializationJobRecord.status,func.count()).group_by(TelemetryMaterializationJobRecord.status).all())
        oldest = self.db.query(func.min(TelemetryMaterializationJobRecord.created_at)).filter(TelemetryMaterializationJobRecord.status=="queued").scalar()
        return {"status":"ready" if workers else "worker_offline", "active_workers":int(workers or 0),
                "last_worker_seen_at":last_seen, "queued_jobs":counts.get("queued",0),
                "running_jobs":counts.get("running",0),"oldest_queued_seconds":max(0,(now-oldest).total_seconds()) if oldest else 0,
                "replay_startup_target_seconds":180}

    def ensure_materialization(
        self,
        request: TelemetryMaterializationRequest,
        *,
        expires_at: datetime,
    ) -> TelemetryMaterializationEnsureResponse:
        self._lock_session(request.session_id, "ensure")
        self._assert_session_exists(request.session_id)
        self._assert_entries_belong_to_session(request.session_id, request.entry_ids)

        if not request.force_refresh:
            self._backfill_completed_segments_from_existing_rows(request, expires_at=expires_at, commit=False)

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
            self.db.commit()
            return TelemetryMaterializationEnsureResponse(ready=True, segments=ready_segments)

        active_job = None if request.force_refresh else self._find_active_job_covering_pairs(request, missing_pairs)
        if active_job is not None:
            self._cancel_queued_jobs_covered_by_record(active_job, commit=False)
            self.db.commit()
            return TelemetryMaterializationEnsureResponse(
                ready=False,
                job_id=active_job.id,
                segments=self.list_segments_for_request(request),
            )

        job = self.create_job(request, expires_at=expires_at, commit=False)
        self.queue_segments(
            request.session_id,
            missing_pairs,
            scope=request.scope,
            lap_number=request.lap_number,
            expires_at=expires_at,
            force_refresh=request.force_refresh,
            commit=False,
        )
        self._cancel_queued_jobs_covered_by_request(request, keep_job_id=job.id, commit=False)
        self.db.commit()
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
        commit: bool = True,
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
        self.db.flush()
        if commit:
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
        commit: bool = True,
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
        self.db.flush()
        if commit:
            self.db.commit()

    def get_job(self, job_id: str) -> TelemetryMaterializationJobRead | None:
        record = self.db.get(TelemetryMaterializationJobRecord, job_id)
        return self.to_job_model(record) if record is not None else None

    def list_jobs(self, *, limit: int = 50) -> list[TelemetryMaterializationJobRead]:
        records = (
            self.db.query(TelemetryMaterializationJobRecord)
            .join(EventSessionRecord, EventSessionRecord.id == TelemetryMaterializationJobRecord.session_id)
            .filter(or_(EventSessionRecord.owner_user_id.is_(None), EventSessionRecord.owner_user_id == self.db.info.get("actor_user_id")))
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

    def build_telemetry_selection(self, job: TelemetryMaterializationJobRecord) -> TelemetrySelection:
        numbers = self.db.query(SessionEntryRecord.car_number).filter(
            SessionEntryRecord.session_id == job.session_id,
            SessionEntryRecord.id.in_(job.entry_ids),
        ).all()
        session = self.db.get(EventSessionRecord, job.session_id)
        origin = session.session_time_origin_utc if session else None
        if origin is None:
            sample = self.db.query(CarTelemetrySampleRecord).join(SessionEntryRecord).filter(
                SessionEntryRecord.session_id == job.session_id,
                CarTelemetrySampleRecord.source_time_utc.is_not(None)).first()
            if sample:
                origin = sample.source_time_utc-timedelta(milliseconds=sample.session_time_ms)
        anchors = self.db.query(SessionEntryRecord.car_number, EntryLapRecord.lap_number, EntryLapRecord.lap_start_time_ms).join(
            EntryLapRecord, EntryLapRecord.session_entry_id == SessionEntryRecord.id).filter(
                SessionEntryRecord.session_id == job.session_id,
                EntryLapRecord.lap_start_time_ms.is_not(None), EntryLapRecord.lap_number > 1).order_by(EntryLapRecord.lap_number).limit(100).all() if origin is None else []
        return TelemetrySelection(
            driver_numbers=frozenset(number for (number,) in numbers),
            kinds=frozenset(job.kinds),
            clock_origin_utc=origin,
            lap_clock_anchors=tuple(tuple(v) for v in anchors),
        )

    def materialize_snapshot(
        self,
        job: TelemetryMaterializationJobRecord,
        snapshot: SessionSnapshot,
        *,
        source_version: str | None,
        heartbeat: Callable[[], None] | None = None,
    ) -> int:
        self._lock_session(job.session_id, "persist")
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

        if job.scope == "session":
            missing_kinds = [kind for kind, rows in (("car", selected_car), ("position", selected_position))
                             if kind in job.kinds and not rows]
            if missing_kinds:
                raise ValueError(
                    f"The data source returned no {' or '.join(missing_kinds)} telemetry for the selected drivers. "
                    "Replay data is unavailable for this session; try another session or retry when the source is available."
                )

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
        session = self.db.get(EventSessionRecord, job.session_id)
        if session and snapshot.session.session_time_origin_utc and session.session_time_origin_utc is None:
            session.session_time_origin_utc = snapshot.session.session_time_origin_utc
        if session and snapshot.session.data_provider:
            session.data_provider = snapshot.session.data_provider
        refresh_race_control(self.db, job.session_id, getattr(snapshot, "race_control_messages", []))
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
        iterator = iter(rows)
        first = next(iterator, None)
        if first is None:
            return 0
        names = list(first)
        target = model.__table__
        # Stream COPY into a transaction-local staging table, then let the real
        # table enforce its FKs and deduplication in one INSERT. No per-row SQL
        # round trips, no giant parameter list, no application-side commit.
        staging = Table(
            "telemetry_stage_" + generate_uuid().replace("-", ""), MetaData(),
            *(Column(name, target.c[name].type) for name in names),
            schema="pg_temp", prefixes=["TEMPORARY"], postgresql_on_commit="DROP",
        )
        connection = self.db.connection()
        staging.create(connection)
        driver_connection = connection.connection.driver_connection
        command = sql.SQL("COPY {} ({}) FROM STDIN").format(
            sql.Identifier(staging.name), sql.SQL(", ").join(map(sql.Identifier, names)),
        )
        with driver_connection.cursor() as cursor:
            with cursor.copy(command) as copy:
                for index, row in enumerate(chain((first,), iterator), start=1):
                    copy.write_row([row[name] for name in names])
                    if heartbeat is not None and index % BULK_INSERT_CHUNK_SIZE == 0:
                        heartbeat()
        statement = pg_insert(target).from_select(names, select(*(staging.c[name] for name in names))).on_conflict_do_nothing(constraint=conflict_constraint)
        written = statement.returning(literal_column("1")).cte("written")
        count = self.db.execute(select(func.count()).select_from(written)).scalar_one()
        if heartbeat is not None:
            heartbeat()
        return int(count)

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
            self.db.query(SessionTickRecord.session_time_ms, SessionTickRecord.id)
            .filter(
                SessionTickRecord.session_id == session_id,
                SessionTickRecord.session_time_ms >= min(payload_by_time),
                SessionTickRecord.session_time_ms <= max(payload_by_time),
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
                if segment is not None and (segment.status != "completed" or segment.row_count == 0):
                    segment.status = "failed"
                    segment.error_message = error_message
                    segment.updated_at = now
                    self.db.add(segment)

    def _backfill_completed_segments_from_existing_rows(
        self,
        request: TelemetryMaterializationRequest,
        *,
        expires_at: datetime,
        commit: bool = True,
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
            self.db.flush()
            if commit:
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
