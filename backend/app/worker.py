from __future__ import annotations

import logging
import time

from app.config import settings
from modules.session_import.application.service import ImportJobService
from modules.storage.infrastructure.db import SessionLocal

logger = logging.getLogger("pitwall.worker")


def run_once() -> bool:
    db = SessionLocal()
    try:
        service = ImportJobService(db=db)
        service.recover_stale_jobs()
        service.cleanup_expired()
        job = service.run_next_job()
        if job is None:
            return False
        logger.info("Processed import job %s with status=%s", job.id, job.status)
        return True
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
