from fastapi import APIRouter
from modules.identity_auth.application.service import AuthService
from modules.identity_auth.infrastructure.repository import AuthSessionRepository

router = APIRouter(prefix="/api/auth", tags=["auth"])

service = AuthService(repository=AuthSessionRepository())


@router.get("/health")
def auth_health() -> dict:
    return {
        "module": "identity_auth",
        "status": "ok",
    }


@router.get("/session")
def get_auth_session() -> dict:
    return service.get_current_session().model_dump()