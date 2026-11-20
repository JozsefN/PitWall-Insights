from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, false
from sqlalchemy.orm import Mapped, mapped_column

from modules.storage.infrastructure.base import Base


class BillingAccountRecord(Base):
    __tablename__ = "billing_accounts"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    subscription_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    plan_code: Mapped[str | None] = mapped_column(String(16))
    interval: Mapped[str | None] = mapped_column(String(8))
    status: Mapped[str | None] = mapped_column(String(32))
    paid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, server_default=false())
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkout_key: Mapped[str | None] = mapped_column(String(64))
    checkout_plan: Mapped[str | None] = mapped_column(String(16))
    checkout_interval: Mapped[str | None] = mapped_column(String(8))
    checkout_id: Mapped[str | None] = mapped_column(String(128))
    checkout_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BillingWebhookEventRecord(Base):
    __tablename__ = "billing_webhook_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.user_id", ondelete="CASCADE"), index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
