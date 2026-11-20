from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.identity_auth.domain.models import User
from modules.identity_auth.infrastructure.db_models import UserRecord


class AuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_id(self, user_id: str) -> User | None:
        record = self.db.get(UserRecord, user_id)
        if record is None or (record.role != "admin" and record.email_verified_at is None):
            return None
        return User(id=record.id, email=record.email, role=record.role,
                    email_verified=record.email_verified_at is not None)

    def account_by_email(self, email: str) -> UserRecord | None:
        matches = self.db.scalars(select(UserRecord).where(func.lower(UserRecord.email) == email.lower()).limit(2)).all()
        if len(matches) == 1:
            return matches[0]
        return next((account for account in matches if account.email == email), None)

    def email_exists(self, email: str) -> bool:
        return self.db.scalar(select(UserRecord.id).where(func.lower(UserRecord.email) == email.lower()).limit(1)) is not None
