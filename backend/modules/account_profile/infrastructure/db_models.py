from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from modules.storage.infrastructure.base import Base


class AccountProfileRecord(Base):
    __tablename__ = "account_profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(120))
    nickname: Mapped[str | None] = mapped_column(String(60))
    phone_number: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
