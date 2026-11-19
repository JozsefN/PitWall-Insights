from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from threading import Event, Thread
from time import perf_counter

from sqlalchemy.orm import Session, sessionmaker

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

logger = logging.getLogger("pitwall.telemetry")


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
        started = perf_counter()
        stop_heartbeat = Event()
        heartbeat = self._build_job_heartbeat(job_id)
        def keep_alive() -> None:
            while not stop_heartbeat.wait(10):
                try:
                    heartbeat()
                except Exception:
                    logger.exception("Could not update telemetry job heartbeat %s", job_id)
        heartbeat_thread = Thread(target=keep_alive, daemon=True)
        heartbeat_thread.start()
        try:
            source, request = self.repository.build_session_import_request(job.session_id)
            request.force_refresh = job.force_refresh
            selection = self.repository.build_telemetry_selection(job)
            from modules.session_domain.infrastructure.models import EventSessionRecord
            session = self.db.get(EventSessionRecord, job.session_id)
            ingestion_service = IngestionService(source=build_session_source(source, db=self.db,
                user_id=session.owner_user_id if session else None, session_id=job.session_id))

            self.repository.mark_stage(job_id, stage="loading_source", now=datetime.now(timezone.utc))
            bundle = ingestion_service.load_session(request, telemetry_selection=selection)
            loaded = perf_counter()
            logger.info("Telemetry job %s source=%.2fs drivers=%s kinds=%s", job_id,
                        loaded - started, len(selection.driver_numbers), sorted(selection.kinds))

            self.repository.mark_stage(job_id, stage="normalizing", now=datetime.now(timezone.utc))
            snapshot = self.normalization_service.build_snapshot(
                bundle=bundle,
                ttl_hours=settings.session_cache_ttl_hours,
            )
            normalized = perf_counter()

            self.repository.mark_stage(job_id, stage="persisting", now=datetime.now(timezone.utc))
            rows_written = self.repository.materialize_snapshot(
                job,
                snapshot,
                source_version=bundle.source_version,
                heartbeat=heartbeat,
            )
            logger.info("Telemetry job %s normalize=%.2fs persist=%.2fs total=%.2fs rows=%s",
                        job_id, normalized - loaded, perf_counter() - normalized,
                        perf_counter() - started, rows_written)

            return self.repository.mark_completed(
                job_id,
                source_version=bundle.source_version,
                rows_written=rows_written,
                now=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.exception("Telemetry job %s failed after %.2fs", job_id, perf_counter() - started)
            self.db.rollback()
            return self.repository.mark_failed(
                job_id,
                error_message=str(exc),
                now=datetime.now(timezone.utc),
            )
        finally:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=2)

    def recover_stale_jobs(self) -> int:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(minutes=settings.import_job_stale_after_minutes)
        return self.repository.recover_stale_running_jobs(
            stale_before=stale_before,
            now=now,
            max_attempts=settings.import_job_max_attempts,
        )

    def _build_job_heartbeat(self, job_id: str):
        factory = sessionmaker(bind=self.db.get_bind(), autoflush=False)
        def heartbeat() -> None:
            heartbeat_db = factory()
            try:
                TelemetryMaterializationRepository(heartbeat_db).touch_heartbeat(
                    job_id,
                    now=datetime.now(timezone.utc),
                )
            finally:
                heartbeat_db.close()

        return heartbeat
