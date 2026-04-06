from sqlalchemy.orm import Session

from modules.identity_auth.domain.models import User
from modules.identity_auth.infrastructure.db_models import UserRecord


class AuthRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        record = (
            self.db.query(UserRecord)
            .filter(UserRecord.email == email)
            .first()
        )

        if record is None:
            return None

        return User(
            id=record.id,
            email=record.email,
        )

    def get_password_hash(self, email: str) -> str | None:
        record = (
            self.db.query(UserRecord)
            .filter(UserRecord.email == email)
            .first()
        )

        if record is None:
            return None

        return record.password_hash

    def create_user(self, email: str, password_hash: str) -> User:
        record = UserRecord(
            email=email,
            password_hash=password_hash,
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        return User(
            id=record.id,
            email=record.email,
        )