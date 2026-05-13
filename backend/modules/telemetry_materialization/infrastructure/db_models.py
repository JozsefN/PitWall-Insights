from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modules.session_domain.infrastructure.models.common import StringIdMixin, utc_now
from modules.storage.infrastructure.base import Base


class TelemetryCacheSegmentRecord(StringIdMixin, Base):
    __tablename__ = "telemetry_cache_segments"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "session_entry_id",
            "kind",
            "scope",
            "lap_number",
            name="uq_telemetry_cache_segment_key",
        ),
        Index("ix_telemetry_cache_segments_session_status", "session_id", "status"),
        Index("ix_telemetry_cache_segments_entry_kind", "session_entry_id", "kind"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_entry_id: Mapped[str] = mapped_column(
        ForeignKey("session_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TelemetryMaterializationJobRecord(StringIdMixin, Base):
    __tablename__ = "telemetry_materialization_jobs"
    __table_args__ = (
        Index("ix_telemetry_jobs_status_created", "status", "created_at"),
        Index("ix_telemetry_jobs_session_status", "session_id", "status"),
        Index("ix_telemetry_jobs_heartbeat", "heartbeat_at"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    kinds: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    progress_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    force_refresh: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rows_written: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
