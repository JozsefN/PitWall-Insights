from modules.session_domain.domain.models import SessionSummary


class SessionRepository:
    def list_sessions(self) -> list[SessionSummary]:
        return [
            SessionSummary(
                id="session-001",
                name="FP1 Mock Session",
                track_code="MONZA",
                driver_code="DRV_A",
                lap_count=12,
            ),
            SessionSummary(
                id="session-002",
                name="Qualifying Mock Session",
                track_code="SPA",
                driver_code="DRV_B",
                lap_count=8,
            ),
        ]

    def get_session(self, session_id: str) -> SessionSummary | None:
        for session in self.list_sessions():
            if session.id == session_id:
                return session
        return None