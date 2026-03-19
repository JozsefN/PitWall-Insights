from fastapi import APIRouter, HTTPException
from modules.session_domain.application.service import SessionService
from modules.session_domain.infrastructure.repository import SessionRepository

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

service = SessionService(repository=SessionRepository())


@router.get("")
def list_sessions() -> list[dict]:
    return [session.model_dump() for session in service.list_sessions()]


@router.get("/{session_id}")
def get_session(session_id: str) -> dict:
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()