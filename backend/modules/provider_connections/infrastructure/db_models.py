from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from modules.storage.infrastructure.base import Base


class F1ConnectionRecord(Base):
    __tablename__ = "f1_account_connections"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="connected", nullable=False)
    auth_method: Mapped[str] = mapped_column(String(16), default="password", server_default="password", nullable=False)
