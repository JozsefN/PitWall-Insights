from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from modules.session_domain.infrastructure.models.common import StringIdMixin, utc_now
from modules.storage.infrastructure.base import Base


class ImportJobRecord(StringIdMixin, Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        Index("ix_import_jobs_status_created", "status", "created_at"),
        Index(
            "ix_import_jobs_source_session_profile_status",
            "source",
            "source_session_key",
            "import_profile",
            "status",
        ),
        Index("ix_import_jobs_user_created", "created_by_user_id", "created_at"),
        Index("ix_import_jobs_heartbeat", "heartbeat_at"),
    )

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_session_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    session_name: Mapped[str] = mapped_column(String(128), nullable=False)
    import_profile: Mapped[str] = mapped_column(String(32), nullable=False, default="core")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    progress_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    force_refresh: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rows_written: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
