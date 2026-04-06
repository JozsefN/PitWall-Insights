from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from modules.identity_auth.application.schemas import (
    AuthSessionResponse,
    AuthTokenResponse,
    LoginRequest,
    SignUpRequest,
)
from modules.identity_auth.application.security import decode_access_token
from modules.identity_auth.application.service import AuthService
from modules.identity_auth.infrastructure.repository import AuthRepository
from modules.storage.infrastructure.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    repository = AuthRepository(db)
    return AuthService(repository=repository)


@router.get("/health")
def auth_health() -> dict:
    return {
        "module": "identity_auth",
        "status": "ok",
    }


@router.post("/signup", response_model=AuthTokenResponse)
def signup(
    payload: SignUpRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    try:
        token = service.signup(payload.email, payload.password)
        return AuthTokenResponse(access_token=token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    try:
        token = service.login(payload.email, payload.password)
        return AuthTokenResponse(access_token=token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/session", response_model=AuthSessionResponse)
def get_auth_session(
    authorization: str | None = Header(default=None),
    service: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    if authorization is None or not authorization.startswith("Bearer "):
        return AuthSessionResponse(
            authenticated=False,
            user_id=None,
            email=None,
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        email = payload.get("email")
        return AuthSessionResponse(
            authenticated=True,
            user_id=user_id,
            email=email,
        )
    except ValueError:
        return AuthSessionResponse(
            authenticated=False,
            user_id=None,
            email=None,
        )