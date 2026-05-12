from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel

from modules.session_domain.domain.models import ImportProfile, TelemetryStatus


class NormalizationStatus(BaseModel):
    pipeline_name: str
    status: str
    canonical_schema_ready: bool


@dataclass(slots=True)
class SeasonPayload:
    year: int
    display_name: str


@dataclass(slots=True)
class WeekendPayload:
    source: str
    source_event_key: str
    season_year: int
    round_number: int | None
    event_name: str
    official_event_name: str | None
    country: str | None
    location: str | None
    event_format: str | None
    is_testing: bool


@dataclass(slots=True)
class SessionPayload:
    source: str
    source_session_key: str
    source_event_key: str
    session_name: str
    session_type: str | None
    import_profile: ImportProfile
    telemetry_status: TelemetryStatus
    meeting_key: str | None
    session_key: str | None
    api_path: str | None
    f1_api_support: bool | None
    scheduled_start_utc: datetime | None
    actual_start_utc: datetime | None
    state: str
    imported_at: datetime
    last_accessed_at: datetime
    expires_at: datetime
    error_message: str | None = None


@dataclass(slots=True)
class DriverPayload:
    source: str
    source_driver_key: str
    driver_number: str | None
    abbreviation: str | None
    broadcast_name: str | None
    first_name: str | None
    last_name: str | None
    full_name: str | None
    country_code: str | None


@dataclass(slots=True)
class TeamPayload:
    source: str
    source_team_key: str
    name: str
    display_name: str | None
    team_color: str | None


@dataclass(slots=True)
class SessionEntryPayload:
    source_entry_key: str
    source_driver_key: str
    source_team_key: str | None
    car_number: str
    entry_type: str
    status: str | None
    grid_position: int | None
    classified_position: int | None


@dataclass(slots=True)
class EntryResultPayload:
    source_entry_key: str
    position: int | None
    classified_position: str | None
    points: float | None
    time_status: str | None
    status: str | None
    laps_completed: int | None
    q1_time_ms: int | None
    q2_time_ms: int | None
    q3_time_ms: int | None


@dataclass(slots=True)
class EntryLapPayload:
    source_entry_key: str
    lap_number: int
    lap_position: int | None
    stint_number: int | None
    lap_time_ms: int | None
    lap_start_time_ms: int | None
    lap_end_time_ms: int | None
    pit_out_time_ms: int | None
    pit_in_time_ms: int | None
    sector_1_time_ms: int | None
    sector_2_time_ms: int | None
    sector_3_time_ms: int | None
    sector_1_session_time_ms: int | None
    sector_2_session_time_ms: int | None
    sector_3_session_time_ms: int | None
    speed_i1_kph: float | None
    speed_i2_kph: float | None
    speed_fl_kph: float | None
    speed_st_kph: float | None
    compound: str | None
    tyre_life: int | None
    fresh_tyre: bool | None
    track_status: str | None
    is_deleted: bool
    deleted_reason: str | None
    is_generated: bool
    is_accurate: bool


@dataclass(slots=True)
class EntryStintPayload:
    source_entry_key: str
    stint_number: int
    compound: str | None
    tyre_life_start: int | None
    tyre_life_end: int | None
    lap_start_number: int | None
    lap_end_number: int | None
    lap_count: int
    started_session_time_ms: int | None
    ended_session_time_ms: int | None


@dataclass(slots=True)
class SessionTickPayload:
    session_time_ms: int
    source_time_utc: datetime | None
    source_kind: str


@dataclass(slots=True)
class SessionWeatherSamplePayload:
    session_time_ms: int
    source_time_utc: datetime | None
    air_temp_c: float | None
    humidity_pct: float | None
    pressure_mbar: float | None
    rainfall: bool | None
    track_temp_c: float | None
    wind_direction_deg: int | None
    wind_speed_kph: float | None


@dataclass(slots=True)
class SessionStatusEventPayload:
    session_time_ms: int
    source_time_utc: datetime | None
    status: str


@dataclass(slots=True)
class SessionTrackStatusEventPayload:
    session_time_ms: int
    source_time_utc: datetime | None
    status: str
    message: str | None


@dataclass(slots=True)
class SessionRaceControlMessagePayload:
    session_time_ms: int
    source_time_utc: datetime | None
    source_entry_key: str | None
    category: str | None
    message: str
    flag: str | None
    scope: str | None
    sector: int | None
    lap_number: int | None
    driver_number: str | None


@dataclass(slots=True)
class CarTelemetrySamplePayload:
    source_entry_key: str
    sample_seq: int
    session_time_ms: int
    source_time_utc: datetime | None
    source: str | None
    lap_number: int | None
    stint_number: int | None
    speed_kph: float | None
    rpm: int | None
    gear: int | None
    throttle_pct: float | None
    brake_on: bool | None
    drs_state: int | None


@dataclass(slots=True)
class PositionSamplePayload:
    source_entry_key: str
    sample_seq: int
    session_time_ms: int
    source_time_utc: datetime | None
    source: str | None
    lap_number: int | None
    stint_number: int | None
    x: float | None
    y: float | None
    z: float | None
    track_status: str | None


@dataclass(slots=True)
class SessionSnapshot:
    season: SeasonPayload
    weekend: WeekendPayload
    session: SessionPayload
    drivers: list[DriverPayload] = field(default_factory=list)
    teams: list[TeamPayload] = field(default_factory=list)
    entries: list[SessionEntryPayload] = field(default_factory=list)
    results: list[EntryResultPayload] = field(default_factory=list)
    laps: list[EntryLapPayload] = field(default_factory=list)
    stints: list[EntryStintPayload] = field(default_factory=list)
    ticks: list[SessionTickPayload] = field(default_factory=list)
    weather_samples: list[SessionWeatherSamplePayload] = field(default_factory=list)
    status_events: list[SessionStatusEventPayload] = field(default_factory=list)
    track_status_events: list[SessionTrackStatusEventPayload] = field(default_factory=list)
    race_control_messages: list[SessionRaceControlMessagePayload] = field(default_factory=list)
    car_samples: list[CarTelemetrySamplePayload] = field(default_factory=list)
    position_samples: list[PositionSamplePayload] = field(default_factory=list)

    def total_row_count(self) -> int:
        return (
            len(self.drivers)
            + len(self.teams)
            + len(self.entries)
            + len(self.results)
            + len(self.laps)
            + len(self.stints)
            + len(self.ticks)
            + len(self.weather_samples)
            + len(self.status_events)
            + len(self.track_status_events)
            + len(self.race_control_messages)
            + len(self.car_samples)
            + len(self.position_samples)
        )
