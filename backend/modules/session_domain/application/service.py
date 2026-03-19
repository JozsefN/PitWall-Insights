from modules.session_domain.domain.models import SessionSummary
from modules.session_domain.infrastructure.repository import SessionRepository


class SessionService:
    def __init__(self, repository: SessionRepository) -> None:
        self.repository = repository

    def list_sessions(self) -> list[SessionSummary]:
        return self.repository.list_sessions()

    def get_session(self, session_id: str) -> SessionSummary | None:
        return self.repository.get_session(session_id)