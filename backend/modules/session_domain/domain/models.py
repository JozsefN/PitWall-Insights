from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ImportProfile = Literal["core", "full"]
TelemetryStatus = Literal["not_loaded", "loaded", "partial", "unavailable"]


class SessionCatalogItem(BaseModel):
    source: str = Field(min_length=1, max_length=32)
    source_event_key: str
    source_session_key: str
    season_year: int
    round_number: int | None = None
    event_name: str
    official_event_name: str | None = None
    country: str | None = None
    location: str | None = None
    event_format: str | None = None
    is_testing: bool = False
    session_name: str
    session_type: str | None = None
    scheduled_start_utc: datetime | None = None


class SessionImportRequest(BaseModel):
    season_year: int = Field(ge=2018, le=2100)
    round_number: int = Field(ge=0)
    session_name: str = Field(min_length=1, max_length=128)
    source_session_key: str | None = Field(default=None, min_length=1, max_length=255)
    import_profile: ImportProfile = "core"
    force_refresh: bool = False


class SessionSummary(BaseModel):
    id: str
    source: str
    source_session_key: str
    season_year: int
    round_number: int | None = None
    event_name: str
    official_event_name: str | None = None
    country: str | None = None
    location: str | None = None
    session_name: str
    session_type: str | None = None
    import_profile: ImportProfile = "core"
    telemetry_status: TelemetryStatus = "not_loaded"
    scheduled_start_utc: datetime | None = None
    actual_start_utc: datetime | None = None
    state: str
    imported_at: datetime
    last_accessed_at: datetime
    expires_at: datetime
    pinned_at: datetime | None = None
    deleted_at: datetime | None = None
    entry_count: int = 0
    tick_count: int = 0


class SessionDetail(SessionSummary):
    meeting_key: str | None = None
    session_key: str | None = None
    api_path: str | None = None
    f1_api_support: bool | None = None
    weather_sample_count: int = 0
    status_event_count: int = 0
    track_status_event_count: int = 0
    race_control_message_count: int = 0


class SessionEntrySummary(BaseModel):
    id: str
    car_number: str
    entry_type: str
    status: str | None = None
    grid_position: int | None = None
    classified_position: int | None = None
    driver_id: str
    driver_number: str | None = None
    driver_abbreviation: str | None = None
    driver_name: str | None = None
    team_id: str | None = None
    team_name: str | None = None
    team_color: str | None = None
    result_position: int | None = None
    laps_completed: int | None = None
    points: float | None = None


class EntryLapModel(BaseModel):
    id: str
    lap_number: int
    lap_position: int | None = None
    stint_number: int | None = None
    lap_time_ms: int | None = None
    lap_start_time_ms: int | None = None
    lap_end_time_ms: int | None = None
    pit_out_time_ms: int | None = None
    pit_in_time_ms: int | None = None
    sector_1_time_ms: int | None = None
    sector_2_time_ms: int | None = None
    sector_3_time_ms: int | None = None
    sector_1_session_time_ms: int | None = None
    sector_2_session_time_ms: int | None = None
    sector_3_session_time_ms: int | None = None
    speed_i1_kph: float | None = None
    speed_i2_kph: float | None = None
    speed_fl_kph: float | None = None
    speed_st_kph: float | None = None
    compound: str | None = None
    tyre_life: int | None = None
    fresh_tyre: bool | None = None
    track_status: str | None = None
    is_deleted: bool
    deleted_reason: str | None = None
    is_generated: bool
    is_accurate: bool


class SessionTickModel(BaseModel):
    id: str
    tick_no: int
    session_time_ms: int
    source_time_utc: datetime | None = None
    source_kind: str


class CarTelemetrySampleModel(BaseModel):
    id: str
    tick_id: str
    lap_id: str | None = None
    stint_id: str | None = None
    sample_seq: int
    session_time_ms: int
    source_time_utc: datetime | None = None
    source: str | None = None
    speed_kph: float | None = None
    rpm: int | None = None
    gear: int | None = None
    throttle_pct: float | None = None
    brake_on: bool | None = None
    drs_state: int | None = None


class PositionSampleModel(BaseModel):
    id: str
    tick_id: str
    lap_id: str | None = None
    stint_id: str | None = None
    sample_seq: int
    session_time_ms: int
    source_time_utc: datetime | None = None
    source: str | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None
    track_status: str | None = None


class DeleteSessionResponse(BaseModel):
    deleted: bool
    session_id: str
