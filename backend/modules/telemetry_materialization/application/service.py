from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from modules.ingestion.application.service import IngestionService
from modules.ingestion.infrastructure.provider_registry import build_session_source
from modules.normalization.application.service import NormalizationService
from modules.telemetry_materialization.domain.models import (
    TelemetryMaterializationEnsureResponse,
    TelemetryMaterializationJobListResponse,
    TelemetryMaterializationJobRead,
    TelemetryMaterializationRequest,
)
from modules.telemetry_materialization.infrastructure.repository import TelemetryMaterializationRepository


class TelemetryMaterializationService:
    def __init__(
        self,
        db: Session,
        *,
        repository: TelemetryMaterializationRepository | None = None,
        normalization_service: NormalizationService | None = None,
    ) -> None:
        self.db = db
        self.repository = repository or TelemetryMaterializationRepository(db)
        self.normalization_service = normalization_service or NormalizationService()

    def ensure_materialization(
        self,
        request: TelemetryMaterializationRequest,
    ) -> TelemetryMaterializationEnsureResponse:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.session_cache_ttl_hours)
        return self.repository.ensure_materialization(request, expires_at=expires_at)

    def get_job(self, job_id: str) -> TelemetryMaterializationJobRead | None:
        return self.repository.get_job(job_id)

    def list_jobs(self, *, limit: int = 50) -> TelemetryMaterializationJobListResponse:
        return TelemetryMaterializationJobListResponse(jobs=self.repository.list_jobs(limit=limit))

    def run_next_job(self) -> TelemetryMaterializationJobRead | None:
        now = datetime.now(timezone.utc)
        job = self.repository.claim_next_job(now=now)
        if job is None:
            return None

        job_id = job.id
        try:
            source, request = self.repository.build_session_import_request(job.session_id)
            ingestion_service = IngestionService(source=build_session_source(source))

            self.repository.mark_stage(job_id, stage="loading_source", now=datetime.now(timezone.utc))
            bundle = ingestion_service.load_session(request)

            self.repository.mark_stage(job_id, stage="normalizing", now=datetime.now(timezone.utc))
            snapshot = self.normalization_service.build_snapshot(
                bundle=bundle,
                ttl_hours=settings.session_cache_ttl_hours,
            )

            self.repository.mark_stage(job_id, stage="persisting", now=datetime.now(timezone.utc))
            rows_written = self.repository.materialize_snapshot(
                job,
                snapshot,
                source_version=bundle.source_version,
                heartbeat=self._build_job_heartbeat(job_id),
            )

            return self.repository.mark_completed(
                job_id,
                source_version=bundle.source_version,
                rows_written=rows_written,
                now=datetime.now(timezone.utc),
            )
        except Exception as exc:
            self.db.rollback()
            return self.repository.mark_failed(
                job_id,
                error_message=str(exc),
                now=datetime.now(timezone.utc),
            )

    def recover_stale_jobs(self) -> int:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(minutes=settings.import_job_stale_after_minutes)
        return self.repository.recover_stale_running_jobs(
            stale_before=stale_before,
            now=now,
            max_attempts=settings.import_job_max_attempts,
        )

    @staticmethod
    def _build_job_heartbeat(job_id: str):
        def heartbeat() -> None:
            from modules.storage.infrastructure.db import SessionLocal

            heartbeat_db = SessionLocal()
            try:
                TelemetryMaterializationRepository(heartbeat_db).touch_heartbeat(
                    job_id,
                    now=datetime.now(timezone.utc),
                )
            finally:
                heartbeat_db.close()

        return heartbeat
