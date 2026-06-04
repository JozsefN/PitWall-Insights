from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from modules.delivery_api.api.auth_dependencies import require_current_user
from modules.session_domain.domain.models import SessionImportRequest
from modules.session_import.application.service import ImportJobService
from modules.session_import.domain.models import ImportJobListResponse, ImportJobRead
from modules.storage.infrastructure.db import get_db

router = APIRouter(
    prefix="/api/session-import/jobs",
    tags=["session-import"],
    dependencies=[Depends(require_current_user)],
)


def build_import_job_service(db: Session) -> ImportJobService:
    return ImportJobService(db=db)


@router.post("", response_model=ImportJobRead, status_code=status.HTTP_202_ACCEPTED)
def create_import_job(
    request: SessionImportRequest,
    db: Session = Depends(get_db),
) -> ImportJobRead:
    service = build_import_job_service(db)
    return service.create_job(request)


@router.get("", response_model=ImportJobListResponse)
def list_import_jobs(
    limit: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ImportJobListResponse:
    service = build_import_job_service(db)
    return service.list_jobs(limit=limit)


@router.get("/{job_id}", response_model=ImportJobRead)
def get_import_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> ImportJobRead:
    service = build_import_job_service(db)
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return job
