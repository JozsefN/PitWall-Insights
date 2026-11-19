"""Transport-level ownership guard covers every API using a private dataset identifier."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from modules.delivery_api.api.auth_dependencies import get_current_user
from modules.storage.infrastructure.db import get_db
from modules.session_domain.infrastructure.models import EventSessionRecord
from modules.session_import.infrastructure.db_models import ImportJobRecord
from modules.telemetry_materialization.infrastructure.db_models import TelemetryMaterializationJobRecord


async def enforce_dataset_access(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if user is None:
        return  # Existing route authentication decides whether this is a public endpoint.
    db.info["actor_user_id"] = user.id
    session_id = request.path_params.get("session_id") or request.query_params.get("session_id")
    if request.method == "POST" and request.url.path.startswith(("/api/sessions", "/api/session-import", "/api/telemetry", "/api/feature-metrics", "/api/strategy")):
        try:
            payload = await request.json()
        except ValueError:
            payload = {}
        if isinstance(payload, dict):
            session_id = session_id or payload.get("session_id")
            key = payload.get("source_session_key")
            if isinstance(key, str) and "~f1:" in key and key.rsplit("~f1:", 1)[1] != user.id:
                raise HTTPException(404, "Session not found")
    job_id = request.path_params.get("job_id")
    if job_id:
        if request.url.path.startswith("/api/session-import/"):
            job = db.get(ImportJobRecord, job_id)
            if job and job.created_by_user_id and job.created_by_user_id != user.id:
                raise HTTPException(404, "Job not found")
        elif request.url.path.startswith("/api/telemetry/"):
            job = db.get(TelemetryMaterializationJobRecord, job_id)
            session_id = job.session_id if job else None
    if isinstance(session_id, str):
        record = db.get(EventSessionRecord, session_id)
        if record and record.owner_user_id and record.owner_user_id != user.id:
            raise HTTPException(404, "Session not found")
