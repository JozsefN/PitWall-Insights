from modules.identity_auth.domain.models import UserSession


class AuthSessionRepository:
    def get_current_session(self) -> UserSession:
        return UserSession(
            authenticated=False,
            user_id=None,
            email=None,
        )