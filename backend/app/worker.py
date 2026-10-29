from __future__ import annotations

import logging
import time
import os
import socket
from datetime import datetime, timezone
from threading import Event, Thread
from contextlib import contextmanager
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from modules.session_import.application.service import ImportJobService
from modules.storage.infrastructure.db import SessionLocal
from modules.telemetry_materialization.application.service import TelemetryMaterializationService
from modules.telemetry_materialization.infrastructure.repository import TelemetryMaterializationRepository
from modules.telemetry_materialization.infrastructure.db_models import TelemetryWorkerHeartbeatRecord

logger = logging.getLogger("pitwall.worker")


@contextmanager
def worker_presence():
    stopped = Event()
    hostname, process_id = socket.gethostname(), os.getpid()
    worker_id = f"{hostname}:{process_id}"
    started = datetime.now(timezone.utc)
    def update():
        with SessionLocal() as db:
            TelemetryMaterializationRepository(db).touch_worker(worker_id,hostname=hostname,process_id=process_id,
                started_at=started,now=datetime.now(timezone.utc))
    def loop():
        while not stopped.is_set():
            try:
                update()
            except SQLAlchemyError:
                logger.warning("Worker heartbeat unavailable; retrying",exc_info=True)
            stopped.wait(10)
    thread = Thread(target=loop,daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set(); thread.join(timeout=3)
        try:
            with SessionLocal() as db:
                db.query(TelemetryWorkerHeartbeatRecord).filter(TelemetryWorkerHeartbeatRecord.worker_id==worker_id).delete()
                db.commit()
        except SQLAlchemyError:
            logger.warning("Could not remove worker heartbeat")


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
    with worker_presence():
        while True:
            try:
                processed = run_once()
            except SQLAlchemyError:
                logger.exception("Worker database unavailable; retrying")
                processed = False
            if not processed:
                time.sleep(settings.import_worker_poll_seconds)


if __name__ == "__main__":
    run_forever()
