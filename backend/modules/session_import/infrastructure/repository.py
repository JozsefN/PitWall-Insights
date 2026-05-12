from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from modules.session_domain.domain.models import SessionImportRequest
from modules.session_import.domain.models import ImportJobRead
from modules.session_import.infrastructure.db_models import ImportJobRecord


class ImportJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_job(
        self,
        request: SessionImportRequest,
        *,
        source: str,
        expires_at: datetime,
        created_by_user_id: str | None = None,
    ) -> ImportJobRead:
        record = ImportJobRecord(
            source=source,
            source_session_key=request.source_session_key,
            season_year=request.season_year,
            round_number=request.round_number,
            session_name=request.session_name,
            import_profile=request.import_profile,
            force_refresh=request.force_refresh,
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self.to_model(record)

    def get_job(self, job_id: str) -> ImportJobRead | None:
        record = self.db.get(ImportJobRecord, job_id)
        return self.to_model(record) if record is not None else None

    def list_jobs(self, *, limit: int = 50) -> list[ImportJobRead]:
        records = (
            self.db.query(ImportJobRecord)
            .order_by(ImportJobRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self.to_model(record) for record in records]

    def claim_next_job(self, *, now: datetime) -> ImportJobRecord | None:
        record = (
            self.db.query(ImportJobRecord)
            .filter(ImportJobRecord.status == "queued")
            .order_by(ImportJobRecord.created_at.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if record is None:
            return None

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

    def mark_stage(self, job_id: str, *, stage: str, now: datetime) -> ImportJobRead | None:
        record = self.db.get(ImportJobRecord, job_id)
        if record is None:
            return None

        record.progress_stage = stage
        record.heartbeat_at = now
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self.to_model(record)

    def mark_completed(
        self,
        job_id: str,
        *,
        session_id: str,
        source_version: str | None,
        rows_written: int,
        now: datetime,
    ) -> ImportJobRead | None:
        record = self.db.get(ImportJobRecord, job_id)
        if record is None:
            return None

        record.status = "completed"
        record.progress_stage = "completed"
        record.session_id = session_id
        record.source_version = source_version
        record.rows_written = rows_written
        record.heartbeat_at = now
        record.finished_at = now
        record.error_message = None
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self.to_model(record)

    def mark_failed(self, job_id: str, *, error_message: str, now: datetime) -> ImportJobRead | None:
        record = self.db.get(ImportJobRecord, job_id)
        if record is None:
            return None

        record.status = "failed"
        record.progress_stage = "failed"
        record.heartbeat_at = now
        record.finished_at = now
        record.error_message = error_message
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self.to_model(record)

    def recover_stale_running_jobs(
        self,
        *,
        stale_before: datetime,
        now: datetime,
        max_attempts: int,
    ) -> int:
        records = (
            self.db.query(ImportJobRecord)
            .filter(
                ImportJobRecord.status == "running",
                ImportJobRecord.heartbeat_at < stale_before,
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
            self.db.add(record)

        if records:
            self.db.commit()
        return len(records)

    def cleanup_expired_jobs(self, *, now: datetime) -> int:
        records = (
            self.db.query(ImportJobRecord)
            .filter(
                ImportJobRecord.expires_at < now,
                ImportJobRecord.status.in_(("completed", "failed", "cancelled")),
            )
            .all()
        )
        for record in records:
            self.db.delete(record)
        if records:
            self.db.commit()
        return len(records)

    @staticmethod
    def to_import_request(record: ImportJobRecord) -> SessionImportRequest:
        return SessionImportRequest(
            season_year=record.season_year,
            round_number=record.round_number,
            session_name=record.session_name,
            source_session_key=record.source_session_key,
            import_profile=record.import_profile,
            force_refresh=record.force_refresh,
        )

    @staticmethod
    def to_model(record: ImportJobRecord) -> ImportJobRead:
        return ImportJobRead(
            id=record.id,
            source=record.source,
            source_session_key=record.source_session_key,
            season_year=record.season_year,
            round_number=record.round_number,
            session_name=record.session_name,
            import_profile=record.import_profile,
            status=record.status,
            progress_stage=record.progress_stage,
            attempt_count=record.attempt_count,
            force_refresh=record.force_refresh,
            created_by_user_id=record.created_by_user_id,
            session_id=record.session_id,
            source_version=record.source_version,
            rows_written=record.rows_written,
            error_message=record.error_message,
            created_at=record.created_at,
            started_at=record.started_at,
            heartbeat_at=record.heartbeat_at,
            finished_at=record.finished_at,
            expires_at=record.expires_at,
        )
