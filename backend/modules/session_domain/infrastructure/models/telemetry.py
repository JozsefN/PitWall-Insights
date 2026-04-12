from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.session_domain.infrastructure.models.common import StringIdMixin
from modules.storage.infrastructure.base import Base


class CarTelemetrySampleRecord(StringIdMixin, Base):
    __tablename__ = "car_telemetry_samples"
    __table_args__ = (
        UniqueConstraint("session_entry_id", "sample_seq", name="uq_car_telemetry_sample_seq"),
        Index("ix_car_telemetry_entry_time", "session_entry_id", "session_time_ms"),
        Index("ix_car_telemetry_tick", "tick_id"),
    )

    session_entry_id: Mapped[str] = mapped_column(
        ForeignKey("session_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tick_id: Mapped[str] = mapped_column(
        ForeignKey("session_ticks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lap_id: Mapped[str | None] = mapped_column(
        ForeignKey("entry_laps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stint_id: Mapped[str | None] = mapped_column(
        ForeignKey("entry_stints.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sample_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    session_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_time_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    speed_kph: Mapped[float | None] = mapped_column(nullable=True)
    rpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gear: Mapped[int | None] = mapped_column(Integer, nullable=True)
    throttle_pct: Mapped[float | None] = mapped_column(nullable=True)
    brake_on: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    drs_state: Mapped[int | None] = mapped_column(Integer, nullable=True)

    entry: Mapped["SessionEntryRecord"] = relationship(back_populates="car_samples")
    tick: Mapped["SessionTickRecord"] = relationship(back_populates="car_samples")
    lap: Mapped["EntryLapRecord | None"] = relationship(back_populates="car_samples")
    stint: Mapped["EntryStintRecord | None"] = relationship(back_populates="car_samples")


class PositionSampleRecord(StringIdMixin, Base):
    __tablename__ = "position_samples"
    __table_args__ = (
        UniqueConstraint("session_entry_id", "sample_seq", name="uq_position_samples_seq"),
        Index("ix_position_samples_entry_time", "session_entry_id", "session_time_ms"),
        Index("ix_position_samples_tick", "tick_id"),
    )

    session_entry_id: Mapped[str] = mapped_column(
        ForeignKey("session_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tick_id: Mapped[str] = mapped_column(
        ForeignKey("session_ticks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lap_id: Mapped[str | None] = mapped_column(
        ForeignKey("entry_laps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    stint_id: Mapped[str | None] = mapped_column(
        ForeignKey("entry_stints.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sample_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    session_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_time_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    x: Mapped[float | None] = mapped_column(nullable=True)
    y: Mapped[float | None] = mapped_column(nullable=True)
    z: Mapped[float | None] = mapped_column(nullable=True)
    track_status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    entry: Mapped["SessionEntryRecord"] = relationship(back_populates="position_samples")
    tick: Mapped["SessionTickRecord"] = relationship(back_populates="position_samples")
    lap: Mapped["EntryLapRecord | None"] = relationship(back_populates="position_samples")
    stint: Mapped["EntryStintRecord | None"] = relationship(back_populates="position_samples")
