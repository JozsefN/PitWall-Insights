from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.session_domain.infrastructure.models.common import StringIdMixin
from modules.storage.infrastructure.base import Base


class SessionEntryRecord(StringIdMixin, Base):
    __tablename__ = "session_entries"
    __table_args__ = (
        UniqueConstraint("session_id", "car_number", name="uq_session_entries_car_number"),
        Index("ix_session_entries_driver", "session_id", "driver_id"),
        Index("ix_session_entries_team", "session_id", "team_id"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("event_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    driver_id: Mapped[str] = mapped_column(
        ForeignKey("drivers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[str | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_entry_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    car_number: Mapped[str] = mapped_column(String(16), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False, default="driver_car")
    status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    grid_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classified_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session: Mapped["EventSessionRecord"] = relationship(back_populates="entries")
    driver: Mapped["DriverRecord"] = relationship(back_populates="entries")
    team: Mapped["TeamRecord | None"] = relationship(back_populates="entries")
    result: Mapped["EntryResultRecord | None"] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        uselist=False,
    )
    laps: Mapped[list["EntryLapRecord"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
    )
    stints: Mapped[list["EntryStintRecord"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
    )
    car_samples: Mapped[list["CarTelemetrySampleRecord"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
    )
    position_samples: Mapped[list["PositionSampleRecord"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
    )
    race_control_messages: Mapped[list["SessionRaceControlMessageRecord"]] = relationship(
        back_populates="entry"
    )


class EntryResultRecord(StringIdMixin, Base):
    __tablename__ = "entry_results"
    __table_args__ = (UniqueConstraint("session_entry_id", name="uq_entry_results_entry"),)

    session_entry_id: Mapped[str] = mapped_column(
        ForeignKey("session_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classified_position: Mapped[str | None] = mapped_column(String(32), nullable=True)
    points: Mapped[float | None] = mapped_column(nullable=True)
    time_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    laps_completed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    q1_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    q2_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    q3_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    entry: Mapped["SessionEntryRecord"] = relationship(back_populates="result")


class EntryLapRecord(StringIdMixin, Base):
    __tablename__ = "entry_laps"
    __table_args__ = (
        UniqueConstraint("session_entry_id", "lap_number", name="uq_entry_laps_number"),
        Index("ix_entry_laps_session_entry", "session_entry_id", "lap_number"),
        Index("ix_entry_laps_time", "session_entry_id", "lap_start_time_ms"),
    )

    session_entry_id: Mapped[str] = mapped_column(
        ForeignKey("session_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lap_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stint_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lap_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    lap_start_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    lap_end_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pit_out_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pit_in_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sector_1_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sector_2_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sector_3_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sector_1_session_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sector_2_session_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sector_3_session_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    speed_i1_kph: Mapped[float | None] = mapped_column(nullable=True)
    speed_i2_kph: Mapped[float | None] = mapped_column(nullable=True)
    speed_fl_kph: Mapped[float | None] = mapped_column(nullable=True)
    speed_st_kph: Mapped[float | None] = mapped_column(nullable=True)
    compound: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tyre_life: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fresh_tyre: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    track_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_accurate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    entry: Mapped["SessionEntryRecord"] = relationship(back_populates="laps")
    car_samples: Mapped[list["CarTelemetrySampleRecord"]] = relationship(back_populates="lap")
    position_samples: Mapped[list["PositionSampleRecord"]] = relationship(back_populates="lap")


class EntryStintRecord(StringIdMixin, Base):
    __tablename__ = "entry_stints"
    __table_args__ = (
        UniqueConstraint("session_entry_id", "stint_number", name="uq_entry_stints_number"),
        Index("ix_entry_stints_session_entry", "session_entry_id", "stint_number"),
    )

    session_entry_id: Mapped[str] = mapped_column(
        ForeignKey("session_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stint_number: Mapped[int] = mapped_column(Integer, nullable=False)
    compound: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tyre_life_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tyre_life_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lap_start_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lap_end_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lap_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_session_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ended_session_time_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    entry: Mapped["SessionEntryRecord"] = relationship(back_populates="stints")
    car_samples: Mapped[list["CarTelemetrySampleRecord"]] = relationship(back_populates="stint")
    position_samples: Mapped[list["PositionSampleRecord"]] = relationship(back_populates="stint")
