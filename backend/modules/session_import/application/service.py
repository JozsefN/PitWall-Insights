from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from modules.ingestion.application.service import IngestionService
from modules.ingestion.infrastructure.provider_registry import build_session_source
from modules.normalization.application.service import NormalizationService
from modules.session_domain.domain.models import SessionImportRequest
from modules.session_domain.infrastructure.repository import SessionRepository
from modules.session_import.domain.models import ImportJobListResponse, ImportJobRead
from modules.session_import.infrastructure.repository import ImportJobRepository


class ImportJobService:
    def __init__(
        self,
        db: Session,
        *,
        job_repository: ImportJobRepository | None = None,
        session_repository: SessionRepository | None = None,
        normalization_service: NormalizationService | None = None,
    ) -> None:
        self.db = db
        self.job_repository = job_repository or ImportJobRepository(db)
        self.session_repository = session_repository or SessionRepository(db)
        self.normalization_service = normalization_service or NormalizationService()

    def create_job(
        self,
        request: SessionImportRequest,
        *,
        created_by_user_id: str | None = None,
        source: str | None = None,
    ) -> ImportJobRead:
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.import_job_retention_hours
        )
        return self.job_repository.create_job(
            request,
            source=source or settings.ingestion_source,
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
        )

    def get_job(self, job_id: str) -> ImportJobRead | None:
        return self.job_repository.get_job(job_id)

    def list_jobs(self, *, limit: int = 50) -> ImportJobListResponse:
        return ImportJobListResponse(jobs=self.job_repository.list_jobs(limit=limit))

    def run_next_job(self) -> ImportJobRead | None:
        now = datetime.now(timezone.utc)
        job = self.job_repository.claim_next_job(now=now)
        if job is None:
            return None

        started_at = now
        job_id = job.id
        try:
            request = self.job_repository.to_import_request(job)
            ingestion_service = IngestionService(source=build_session_source(job.source))

            self.job_repository.mark_stage(job_id, stage="loading_source", now=datetime.now(timezone.utc))
            bundle = ingestion_service.load_session(request)

            self.job_repository.mark_stage(job_id, stage="normalizing", now=datetime.now(timezone.utc))
            snapshot = self.normalization_service.build_snapshot(
                bundle=bundle,
                ttl_hours=settings.session_cache_ttl_hours,
            )

            self.job_repository.mark_stage(job_id, stage="persisting", now=datetime.now(timezone.utc))
            session_id = self.session_repository.import_snapshot(
                snapshot,
                source_version=bundle.source_version,
                force_refresh=request.force_refresh,
                job_id=job_id,
                started_at=started_at,
            )

            return self.job_repository.mark_completed(
                job_id,
                session_id=session_id,
                source_version=bundle.source_version,
                rows_written=snapshot.total_row_count(),
                now=datetime.now(timezone.utc),
            )
        except Exception as exc:
            self.db.rollback()
            return self.job_repository.mark_failed(
                job_id,
                error_message=str(exc),
                now=datetime.now(timezone.utc),
            )

    def recover_stale_jobs(self) -> int:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(minutes=settings.import_job_stale_after_minutes)
        return self.job_repository.recover_stale_running_jobs(
            stale_before=stale_before,
            now=now,
            max_attempts=settings.import_job_max_attempts,
        )

    def cleanup_expired(self) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        return {
            "sessions": self.session_repository.cleanup_expired_sessions(now=now),
            "jobs": self.job_repository.cleanup_expired_jobs(now=now),
        }
