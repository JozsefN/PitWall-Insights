import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from modules.storage.infrastructure.base import Base


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role in ('member', 'admin')", name="ck_users_role"),)

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
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(String(16), server_default="member")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailVerificationRecord(Base):
    __tablename__ = "email_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    recipient_key: Mapped[str] = mapped_column(String(64), index=True)
    client_key: Mapped[str] = mapped_column(String(64), index=True)
    code_digest: Mapped[str] = mapped_column(String(64))
    account_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_subject: Mapped[str | None] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
