from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from modules.ingestion.application.service import IngestionService
from modules.ingestion.infrastructure.source_adapter import IngestionSourceAdapter
from modules.normalization.application.service import NormalizationService
from modules.session_domain.application.service import SessionService
from modules.session_domain.domain.models import DeleteSessionResponse, SessionImportRequest
from modules.session_domain.infrastructure.repository import SessionRepository
from modules.storage.infrastructure.db import get_db

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def build_session_service(db: Session) -> SessionService:
    repository = SessionRepository(db=db)
    ingestion_service = IngestionService(source_adapter=IngestionSourceAdapter())
    normalization_service = NormalizationService()
    return SessionService(
        repository=repository,
        ingestion_service=ingestion_service,
        normalization_service=normalization_service,
    )


@router.get("/catalog")
def list_session_catalog(
    season: int | None = Query(default=None, ge=2018, le=2100),
    db: Session = Depends(get_db),
) -> list[dict]:
    service = build_session_service(db)
    season_year = season or datetime.now().year
    return [item.model_dump() for item in service.list_catalog(season_year)]


@router.post("/import", status_code=status.HTTP_201_CREATED)
def import_session(
    request: SessionImportRequest,
    db: Session = Depends(get_db),
) -> dict:
    service = build_session_service(db)
    try:
        return service.import_session(request).model_dump()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("")
def list_sessions(db: Session = Depends(get_db)) -> list[dict]:
    service = build_session_service(db)
    return [session.model_dump() for session in service.list_sessions()]


@router.get("/{session_id}")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> dict:
    service = build_session_service(db)

    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.model_dump()


@router.delete("/{session_id}")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> DeleteSessionResponse:
    service = build_session_service(db)
    deleted = service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return DeleteSessionResponse(deleted=True, session_id=session_id)


@router.get("/{session_id}/entries")
def list_session_entries(
    session_id: str,
    db: Session = Depends(get_db),
) -> list[dict]:
    service = build_session_service(db)
    if service.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return [entry.model_dump() for entry in service.list_entries(session_id)]


@router.get("/{session_id}/entries/{entry_id}/laps")
def list_entry_laps(
    session_id: str,
    entry_id: str,
    db: Session = Depends(get_db),
) -> list[dict]:
    service = build_session_service(db)
    try:
        return [lap.model_dump() for lap in service.list_entry_laps(session_id, entry_id)]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{session_id}/entries/{entry_id}/telemetry/car")
def list_car_telemetry(
    session_id: str,
    entry_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=20000),
    lap_number: int | None = Query(default=None, ge=1),
    session_time_from_ms: int | None = Query(default=None, ge=0),
    session_time_to_ms: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> list[dict]:
    service = build_session_service(db)
    try:
        return [
            sample.model_dump()
            for sample in service.list_car_telemetry(
                session_id,
                entry_id,
                offset=offset,
                limit=limit,
                lap_number=lap_number,
                session_time_from_ms=session_time_from_ms,
                session_time_to_ms=session_time_to_ms,
            )
        ]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{session_id}/entries/{entry_id}/telemetry/position")
def list_position_telemetry(
    session_id: str,
    entry_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=20000),
    lap_number: int | None = Query(default=None, ge=1),
    session_time_from_ms: int | None = Query(default=None, ge=0),
    session_time_to_ms: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> list[dict]:
    service = build_session_service(db)
    try:
        return [
            sample.model_dump()
            for sample in service.list_position_telemetry(
                session_id,
                entry_id,
                offset=offset,
                limit=limit,
                lap_number=lap_number,
                session_time_from_ms=session_time_from_ms,
                session_time_to_ms=session_time_to_ms,
            )
        ]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{session_id}/ticks")
def list_session_ticks(
    session_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=5000, ge=1, le=50000),
    db: Session = Depends(get_db),
) -> list[dict]:
    service = build_session_service(db)
    if service.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return [
        tick.model_dump()
        for tick in service.list_ticks(session_id, offset=offset, limit=limit)
    ]
