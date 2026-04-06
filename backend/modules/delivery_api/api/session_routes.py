from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from modules.session_domain.application.service import SessionService
from modules.session_domain.infrastructure.repository import SessionRepository
from modules.storage.infrastructure.db import get_db

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
def list_sessions(db: Session = Depends(get_db)) -> list[dict]:
    repository = SessionRepository(db=db)
    service = SessionService(repository=repository)
    return [session.model_dump() for session in service.list_sessions()]


@router.get("/{session_id}")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> dict:
    repository = SessionRepository(db=db)
    service = SessionService(repository=repository)

    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.model_dump()