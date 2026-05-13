from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from modules.storage.infrastructure.db import get_db
from modules.telemetry_materialization.application.service import TelemetryMaterializationService
from modules.telemetry_materialization.domain.models import (
    TelemetryMaterializationEnsureResponse,
    TelemetryMaterializationJobListResponse,
    TelemetryMaterializationJobRead,
    TelemetryMaterializationRequest,
)

router = APIRouter(prefix="/api/telemetry/materialization", tags=["telemetry-materialization"])


def build_telemetry_materialization_service(db: Session) -> TelemetryMaterializationService:
    return TelemetryMaterializationService(db=db)


@router.post("/ensure", response_model=TelemetryMaterializationEnsureResponse, status_code=status.HTTP_202_ACCEPTED)
def ensure_telemetry_materialization(
    request: TelemetryMaterializationRequest,
    db: Session = Depends(get_db),
) -> TelemetryMaterializationEnsureResponse:
    service = build_telemetry_materialization_service(db)
    try:
        return service.ensure_materialization(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs", response_model=TelemetryMaterializationJobListResponse)
def list_telemetry_materialization_jobs(
    limit: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> TelemetryMaterializationJobListResponse:
    service = build_telemetry_materialization_service(db)
    return service.list_jobs(limit=limit)


@router.get("/jobs/{job_id}", response_model=TelemetryMaterializationJobRead)
def get_telemetry_materialization_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> TelemetryMaterializationJobRead:
    service = build_telemetry_materialization_service(db)
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Telemetry materialization job not found")
    return job
