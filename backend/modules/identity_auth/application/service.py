from modules.identity_auth.domain.models import UserSession
from modules.identity_auth.infrastructure.repository import AuthSessionRepository


class AuthService:
    def __init__(self, repository: AuthSessionRepository) -> None:
        self.repository = repository

    def get_current_session(self) -> UserSession:
        return self.repository.get_current_session()