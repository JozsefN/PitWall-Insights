import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from modules.storage.infrastructure.base import Base


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )