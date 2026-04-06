from modules.identity_auth.infrastructure.repository import AuthRepository
from modules.identity_auth.application.security import (
    hash_password,
    verify_password,
    create_access_token,
)
from modules.identity_auth.domain.models import UserSession


class AuthService:
    def __init__(self, repository: AuthRepository) -> None:
        self.repository = repository

    def signup(self, email: str, password: str) -> str:
        print("EMAIL:", email)
        print("PASSWORD RAW:", password)
        print("PASSWORD REPR:", repr(password))
        print("PASSWORD LENGTH:", len(password))
        print("PASSWORD BYTES:", len(password.encode("utf-8")))

        existing = self.repository.get_user_by_email(email)
        if existing:
            raise ValueError("User already exists")

        hashed = hash_password(password)
        user = self.repository.create_user(email, hashed)

        return create_access_token(user.id, user.email)

    def login(self, email: str, password: str) -> str:
        user = self.repository.get_user_by_email(email)
        if not user:
            raise ValueError("Invalid credentials")

        password_hash = self.repository.get_password_hash(email)
        if not password_hash:
            raise ValueError("Invalid credentials")

        if not verify_password(password, password_hash):
            raise ValueError("Invalid credentials")

        return create_access_token(user.id, user.email)

    def build_session(self, user_id: str | None, email: str | None) -> UserSession:
        if user_id is None:
            return UserSession(authenticated=False, user_id=None, email=None)

        return UserSession(
            authenticated=True,
            user_id=user_id,
            email=email,
        )