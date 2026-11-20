from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import compare_digest, token_urlsafe

import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from pydantic import EmailStr, TypeAdapter
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from modules.identity_auth.application.email_verification import EmailVerification
from modules.identity_auth.application.schemas import AuthResult, AuthTokenResponse
from modules.identity_auth.application.security import create_access_token, verify_password
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.identity_auth.infrastructure.google_models import GoogleIdentityRecord, GoogleLoginChallengeRecord
from modules.identity_auth.infrastructure.repository import AuthRepository


def nonce_digest(nonce: str) -> str:
    return sha256(nonce.encode()).hexdigest()


def issue_challenge(db: Session, user_id: str | None) -> str:
    now = datetime.now(timezone.utc)
    db.execute(delete(GoogleLoginChallengeRecord).where(GoogleLoginChallengeRecord.expires_at <= now))
    nonce = token_urlsafe(32)
    db.add(GoogleLoginChallengeRecord(nonce_digest=nonce_digest(nonce), user_id=user_id, expires_at=now + timedelta(minutes=10)))
    db.commit()
    return nonce


def verify_google(credential: str, client_id: str) -> dict:
    class TimedRequest(Request):
        def __call__(self, *args, **kwargs):
            kwargs["timeout"] = 5
            return super().__call__(*args, **kwargs)

    with requests.Session() as session:
        try:
            return id_token.verify_oauth2_token(credential, TimedRequest(session), client_id)
        except (GoogleAuthError, ValueError) as error:
            raise ValueError("Google sign-in could not be verified.") from error


def complete_sign_in(db: Session, claims: dict, nonce: str, link_user_id: str | None,
                     password: str | None, client: str) -> AuthResult:
    subject = claims.get("sub")
    claimed_nonce = claims.get("nonce")
    if (
        not isinstance(subject, str) or not 1 <= len(subject) <= 255
        or claims.get("email_verified") is not True
        or not isinstance(claimed_nonce, str) or not compare_digest(nonce.encode(), claimed_nonce.encode())
    ):
        raise ValueError("Google sign-in could not be verified.")
    digest = nonce_digest(nonce)
    challenge = db.get(GoogleLoginChallengeRecord, digest, with_for_update=True)
    if not challenge or challenge.user_id != link_user_id or challenge.expires_at <= datetime.now(timezone.utc):
        raise ValueError("Google sign-in expired. Start again.")
    db.delete(challenge)
    db.commit()

    email = TypeAdapter(EmailStr).validate_python(claims.get("email")).lower()
    if len(email) > 255:
        raise ValueError("Google sign-in could not be completed.")
    authoritative_email = email.endswith("@gmail.com") or bool(claims.get("hd"))
    identity = db.get(GoogleIdentityRecord, subject)
    if link_user_id:
        user = db.get(UserRecord, link_user_id, with_for_update=True)
        if not user or not password or not user.password_hash or not verify_password(password, user.password_hash):
            raise ValueError("Enter your current PitWall password to link Google.")
        if identity and identity.user_id == user.id:
            return AuthTokenResponse(access_token=create_access_token(user.id, user.email))
        if identity or db.scalar(select(GoogleIdentityRecord).where(GoogleIdentityRecord.user_id == user.id)):
            raise ValueError("This Google or PitWall account is already linked.")
    elif identity:
        user = db.get(UserRecord, identity.user_id)
        if not user:
            raise ValueError("Google sign-in could not be completed.")
        if user.role != "admin" and user.email_verified_at is None:
            if not authoritative_email or user.email.lower() != email:
                return EmailVerification(db).issue(user.email, client, account_id=user.id, google_subject=subject)
            user.email_verified_at = datetime.now(timezone.utc)
            db.commit()
        return AuthTokenResponse(access_token=create_access_token(user.id, user.email))
    else:
        if AuthRepository(db).email_exists(email):
            raise ValueError("Sign in with your PitWall password, then link Google from your profile.")
        if not authoritative_email:
            return EmailVerification(db).issue(email, client, google_subject=subject)
        user = UserRecord(email=email, email_verified_at=datetime.now(timezone.utc))
        db.add(user)

    try:
        db.flush()
        db.add(GoogleIdentityRecord(subject=subject, user_id=user.id))
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ValueError("This Google or PitWall account is already linked. Start again.") from error
    return AuthTokenResponse(access_token=create_access_token(user.id, user.email))
