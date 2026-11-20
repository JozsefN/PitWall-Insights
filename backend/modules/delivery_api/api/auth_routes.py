from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from modules.identity_auth.application.schemas import (
    AuthSessionResponse,
    AuthResult,
    AuthTokenResponse,
    LoginRequest,
    SignUpRequest,
    VerificationChallengeRequest,
    VerificationRequest,
    VerificationRequired,
)
from modules.identity_auth.application.email_verification import VerificationThrottled
from modules.identity_auth.application.security import create_access_token
from modules.delivery_api.api.auth_dependencies import get_current_user, require_admin, require_current_user
from modules.identity_auth.domain.models import User
from modules.identity_auth.infrastructure.mailer import MailUnavailable, mail_configured
from modules.identity_auth.application.service import AuthService
from modules.identity_auth.infrastructure.repository import AuthRepository
from modules.storage.infrastructure.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    repository = AuthRepository(db)
    return AuthService(repository=repository)


@router.get("/health", dependencies=[Depends(require_admin)])
def auth_health() -> dict:
    return {
        "module": "identity_auth",
        "status": "ok",
    }


def client_address(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def auth_operation(operation, *, bad_request: int = 400):
    try:
        return operation()
    except MailUnavailable as error:
        raise HTTPException(503, str(error)) from error
    except VerificationThrottled as error:
        raise HTTPException(429, str(error)) from error
    except ValueError as error:
        raise HTTPException(bad_request, str(error)) from error


@router.get("/config")
def auth_config():
    return {"email_verification_available": mail_configured()}


@router.post("/signup", response_model=VerificationRequired, status_code=202)
def signup(
    payload: SignUpRequest,
    request: Request, response: Response,
    service: AuthService = Depends(get_auth_service),
) -> VerificationRequired:
    response.headers["Cache-Control"] = "no-store"
    return auth_operation(lambda: service.signup(payload.email, payload.password, client_address(request)))


@router.post("/login", response_model=AuthResult)
def login(
    payload: LoginRequest,
    request: Request, response: Response,
    service: AuthService = Depends(get_auth_service),
) -> AuthResult:
    response.headers["Cache-Control"] = "no-store"
    return auth_operation(lambda: service.login(payload.email, payload.password, client_address(request)), bad_request=401)


@router.post("/verify-email", response_model=AuthTokenResponse)
def verify_email(payload: VerificationRequest, response: Response, service: AuthService = Depends(get_auth_service)):
    response.headers["Cache-Control"] = "no-store"
    return auth_operation(lambda: service.verification.verify(payload.challenge_id, payload.code))


@router.post("/resend-code", response_model=VerificationRequired)
def resend_code(payload: VerificationChallengeRequest, request: Request, response: Response,
                service: AuthService = Depends(get_auth_service)):
    response.headers["Cache-Control"] = "no-store"
    return auth_operation(lambda: service.verification.resend(payload.challenge_id, client_address(request)))


@router.get("/session", response_model=AuthSessionResponse)
def get_auth_session(
    response: Response, user: User | None = Depends(get_current_user),
) -> AuthSessionResponse:
    response.headers["Cache-Control"] = "no-store"
    if user is None:
        return AuthSessionResponse(authenticated=False)
    return AuthSessionResponse(authenticated=True, user_id=user.id, email=user.email,
                               role=user.role, email_verified=user.email_verified)


@router.post("/refresh", response_model=AuthTokenResponse)
def refresh_auth_token(user: User = Depends(require_current_user)) -> AuthTokenResponse:
    """Renew active sessions only. Expired or invalid tokens still require sign-in."""
    return AuthTokenResponse(access_token=create_access_token(user.id, user.email))
