from sqlalchemy.orm import Session

from modules.session_domain.domain.models import SessionSummary
from modules.session_domain.infrastructure.db_models import SessionRecord


class SessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_sessions(self) -> list[SessionSummary]:
        records = self.db.query(SessionRecord).order_by(SessionRecord.name.asc()).all()

        return [
            SessionSummary(
                id=record.id,
                name=record.name,
                track_code=record.track_code,
                driver_code=record.driver_code,
                lap_count=record.lap_count,
            )
            for record in records
        ]

    def get_session(self, session_id: str) -> SessionSummary | None:
        record = (
            self.db.query(SessionRecord)
            .filter(SessionRecord.id == session_id)
            .first()
        )

        if record is None:
            return None

        return SessionSummary(
            id=record.id,
            name=record.name,
            track_code=record.track_code,
            driver_code=record.driver_code,
            lap_count=record.lap_count,
        )