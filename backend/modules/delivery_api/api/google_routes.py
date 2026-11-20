from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from modules.delivery_api.api.auth_dependencies import get_current_user, require_current_user
from modules.delivery_api.api.auth_routes import auth_operation, client_address
from modules.identity_auth.application.google import complete_sign_in, issue_challenge, verify_google
from modules.identity_auth.application.schemas import AuthResult
from modules.identity_auth.domain.models import User
from modules.identity_auth.infrastructure.google_models import GoogleIdentityRecord
from modules.storage.infrastructure.db import get_db

router = APIRouter(prefix="/api/auth/google", tags=["auth"])


class GoogleChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["signin", "link"]


class GoogleSignInRequest(GoogleChallengeRequest):
    nonce: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$")
    credential: SecretStr = Field(min_length=100, max_length=8192)
    password: SecretStr | None = Field(default=None, max_length=128)


def configured_client() -> str:
    if not settings.google_client_id:
        raise HTTPException(503, "Google sign-in is not configured.")
    return settings.google_client_id


def link_owner(action: str, user: User | None) -> str | None:
    if action == "link":
        if not user:
            raise HTTPException(401, "Sign in before linking Google.")
        return user.id
    return None


@router.get("/config")
def google_config():
    return {"enabled": bool(settings.google_client_id)}


@router.get("/connection")
def google_connection(response: Response, user: User = Depends(require_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return {"linked": bool(db.scalar(select(GoogleIdentityRecord.subject).where(GoogleIdentityRecord.user_id == user.id)))}


@router.post("/challenge")
def challenge(payload: GoogleChallengeRequest, response: Response, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    client = configured_client()
    return {"client_id": client, "nonce": issue_challenge(db, link_owner(payload.action, user))}


@router.post("", response_model=AuthResult)
def google_login(payload: GoogleSignInRequest, request: Request, response: Response,
                 user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    client = configured_client()
    owner = link_owner(payload.action, user)
    def sign_in():
        claims = verify_google(payload.credential.get_secret_value(), client)
        password = payload.password.get_secret_value() if payload.password else None
        return complete_sign_in(db, claims, payload.nonce, owner, password, client_address(request))
    return auth_operation(sign_in)
