from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from modules.session_domain.infrastructure.models.common import StringIdMixin
from modules.storage.infrastructure.base import Base


class SeasonRecord(Base):
    __tablename__ = "seasons"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(32), nullable=False)

    weekends: Mapped[list["WeekendRecord"]] = relationship(
        back_populates="season",
        cascade="all, delete-orphan",
    )


class WeekendRecord(StringIdMixin, Base):
    __tablename__ = "event_weekends"
    __table_args__ = (
        UniqueConstraint("source", "source_event_key", name="uq_weekends_source_key"),
        Index("ix_weekends_season_round", "season_year", "round_number"),
    )

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    season_year: Mapped[int] = mapped_column(
        ForeignKey("seasons.year", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    round_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False)
    official_event_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_format: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_testing: Mapped[bool] = mapped_column(nullable=False, default=False)

    season: Mapped["SeasonRecord"] = relationship(back_populates="weekends")
    sessions: Mapped[list["EventSessionRecord"]] = relationship(
        back_populates="weekend",
        cascade="all, delete-orphan",
    )


class DriverRecord(StringIdMixin, Base):
    __tablename__ = "drivers"
    __table_args__ = (
        UniqueConstraint("source", "source_driver_key", name="uq_drivers_source_key"),
        Index("ix_drivers_abbreviation", "abbreviation"),
    )

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_driver_key: Mapped[str] = mapped_column(String(128), nullable=False)
    driver_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    abbreviation: Mapped[str | None] = mapped_column(String(16), nullable=True)
    broadcast_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)

    entries: Mapped[list["SessionEntryRecord"]] = relationship(back_populates="driver")


class TeamRecord(StringIdMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("source", "source_team_key", name="uq_teams_source_key"),
        Index("ix_teams_name", "name"),
    )

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_team_key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team_color: Mapped[str | None] = mapped_column(String(16), nullable=True)

    entries: Mapped[list["SessionEntryRecord"]] = relationship(back_populates="team")
