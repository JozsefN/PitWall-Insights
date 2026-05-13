from __future__ import annotations

import logging
import time

from app.config import settings
from modules.session_import.application.service import ImportJobService
from modules.storage.infrastructure.db import SessionLocal
from modules.telemetry_materialization.application.service import TelemetryMaterializationService

logger = logging.getLogger("pitwall.worker")


def run_once() -> bool:
    db = SessionLocal()
    try:
        import_service = ImportJobService(db=db)
        telemetry_service = TelemetryMaterializationService(db=db)

        import_service.recover_stale_jobs()
        telemetry_service.recover_stale_jobs()

        job = import_service.run_next_job()
        if job is not None:
            logger.info("Processed import job %s with status=%s", job.id, job.status)
            return True

        telemetry_job = telemetry_service.run_next_job()
        if telemetry_job is not None:
            logger.info(
                "Processed telemetry materialization job %s with status=%s",
                telemetry_job.id,
                telemetry_job.status,
            )
            return True

        import_service.cleanup_expired(include_sessions=False)
        return False
    finally:
        db.close()


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting import worker")
    while True:
        processed = run_once()
        if not processed:
            time.sleep(settings.import_worker_poll_seconds)


if __name__ == "__main__":
    run_forever()
