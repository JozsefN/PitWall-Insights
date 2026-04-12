from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from modules.identity_auth.application.security import decode_access_token
from modules.identity_auth.domain.models import User
from modules.identity_auth.infrastructure.repository import AuthRepository
from modules.storage.infrastructure.db import get_db


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    if authorization is None or not authorization.startswith("Bearer "):
        return None

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = decode_access_token(token)
    except ValueError:
        return None

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        return None

    repository = AuthRepository(db)
    return repository.get_user_by_id(user_id)


def require_current_user(
    user: User | None = Depends(get_current_user),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return user
