from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.session_domain.infrastructure.models.common import StringIdMixin
from modules.storage.infrastructure.base import Base


class EventSessionRecord(StringIdMixin, Base):
    __tablename__ = "event_sessions"
    __table_args__ = (
        UniqueConstraint("source", "source_session_key", name="uq_sessions_source_key"),
        Index("ix_sessions_state_expires", "state", "expires_at"),
        Index("ix_sessions_deleted_expires", "deleted_at", "expires_at"),
        Index("ix_sessions_weekend_name", "weekend_id", "session_name"),
    )

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_session_key: Mapped[str] = mapped_column(String(255), nullable=False)
    weekend_id: Mapped[str] = mapped_column(
        ForeignKey("event_weekends.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_name: Mapped[str] = mapped_column(String(128), nullable=False)
    session_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    import_profile: Mapped[str] = mapped_column(String(32), nullable=False, default="core")
    telemetry_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_loaded")
    meeting_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    f1_api_support: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    scheduled_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="cached")
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    weekend: Mapped["WeekendRecord"] = relationship(back_populates="sessions")
    ingestion_runs: Mapped[list["IngestionRunRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    entries: Mapped[list["SessionEntryRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    weather_samples: Mapped[list["SessionWeatherSampleRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    status_events: Mapped[list["SessionStatusEventRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    track_status_events: Mapped[list["SessionTrackStatusEventRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    race_control_messages: Mapped[list["SessionRaceControlMessageRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    ticks: Mapped[list["SessionTickRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class IngestionRunRecord(StringIdMixin, Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_ingestion_runs_session_started", "session_id", "started_at"),
        Index("ix_ingestion_runs_job_id", "job_id"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_version: Mapped[str | None] = mapped_column("fastf1_version", String(32), nullable=True)
    import_profile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rows_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    force_refresh: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped["EventSessionRecord"] = relationship(back_populates="ingestion_runs")


class SessionTickRecord(StringIdMixin, Base):
    __tablename__ = "session_ticks"
    __table_args__ = (
        UniqueConstraint("session_id", "tick_no", name="uq_session_ticks_tick_no"),
        UniqueConstraint("session_id", "session_time_ms", name="uq_session_ticks_time"),
        Index("ix_session_ticks_session_time", "session_id", "session_time_ms"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tick_no: Mapped[int] = mapped_column(Integer, nullable=False)
    session_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_time_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(128), nullable=False)

    session: Mapped["EventSessionRecord"] = relationship(back_populates="ticks")
    car_samples: Mapped[list["CarTelemetrySampleRecord"]] = relationship(back_populates="tick")
    position_samples: Mapped[list["PositionSampleRecord"]] = relationship(back_populates="tick")


class SessionWeatherSampleRecord(StringIdMixin, Base):
    __tablename__ = "session_weather_samples"
    __table_args__ = (Index("ix_session_weather_time", "session_id", "session_time_ms"),)

    session_id: Mapped[str] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_time_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    air_temp_c: Mapped[float | None] = mapped_column(nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(nullable=True)
    pressure_mbar: Mapped[float | None] = mapped_column(nullable=True)
    rainfall: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    track_temp_c: Mapped[float | None] = mapped_column(nullable=True)
    wind_direction_deg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wind_speed_kph: Mapped[float | None] = mapped_column(nullable=True)

    session: Mapped["EventSessionRecord"] = relationship(back_populates="weather_samples")


class SessionStatusEventRecord(StringIdMixin, Base):
    __tablename__ = "session_status_events"
    __table_args__ = (Index("ix_session_status_time", "session_id", "session_time_ms"),)

    session_id: Mapped[str] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_time_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)

    session: Mapped["EventSessionRecord"] = relationship(back_populates="status_events")


class SessionTrackStatusEventRecord(StringIdMixin, Base):
    __tablename__ = "session_track_status_events"
    __table_args__ = (Index("ix_track_status_time", "session_id", "session_time_ms"),)

    session_id: Mapped[str] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_time_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped["EventSessionRecord"] = relationship(back_populates="track_status_events")


class SessionRaceControlMessageRecord(StringIdMixin, Base):
    __tablename__ = "session_race_control_messages"
    __table_args__ = (Index("ix_race_control_time", "session_id", "session_time_ms"),)

    session_id: Mapped[str] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("session_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_time_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    flag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sector: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lap_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    driver_number: Mapped[str | None] = mapped_column(String(16), nullable=True)

    session: Mapped["EventSessionRecord"] = relationship(back_populates="race_control_messages")
    entry: Mapped["SessionEntryRecord | None"] = relationship(back_populates="race_control_messages")
