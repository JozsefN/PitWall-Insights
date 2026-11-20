from dataclasses import dataclass, field
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

MODEL_VERSION = "race_estimation_v2"
EVENT_TYPES = (
    "braking_anomaly",
    "traction_disruption",
    "possible_incident",
    "stopped_car",
    "overtake",
    "pit_stop",
    "pit_stop_delay",
    "yellow_flag",
    "safety_car",
    "red_flag",
    "green_flag",
    "track_status",
    "track_limits",
    "contact_report",
    "damage_report",
    "personal_best",
    "session_best",
    "traffic_pressure",
)


class ModelAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    wake_loss_at_10m_pct: float = Field(18, ge=0, le=40)
    wake_decay_m: float = Field(6.65, ge=3, le=100)
    max_wake_loss_pct: float = Field(35, ge=0, le=60)
    downforce_weight_ratio_at_200kph: float = Field(2.5, ge=0.5, le=6)
    tyre_cooling_time_s: float = Field(60, ge=15, le=300)
    close_gap_s: float = Field(0.4, ge=0.1, le=2)
    traffic_gap_s: float = Field(2, ge=0.5, le=5)
    source_report_delay_ms: int = Field(1000, ge=0, le=30000)
    max_report_age_ms: int = Field(8000, ge=2000, le=30000)
    max_telemetry_gap_ms: int = Field(2000, ge=500, le=5000)
    position_scale_m_per_unit: float = Field(0.1, ge=0.001, le=100)
    # XYZ has no documented north axis. This must be an explicit, calibrated transform.
    north_rotation_deg: float | None = Field(None, ge=-360, le=360)
    wind_direction_is_from: bool | None = None
    pit_loss_scenario_s: float = Field(22, ge=5, le=60)
    fresh_tyre_gain_scenario_s: float = Field(0.8, ge=0, le=4)


class RaceEstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of_ms: int = Field(ge=0, le=86_400_000)
    entry_ids: list[str] | None = Field(None, min_length=1, max_length=64)
    lookback_ms: int = Field(300000, ge=30000, le=1800000)
    sample_interval_ms: int = Field(500, ge=250, le=1000)
    prediction_horizon_s: float = Field(10, ge=1, le=120)
    max_events: int = Field(500, ge=0, le=1000)
    assumptions: ModelAssumptions = Field(default_factory=ModelAssumptions)


class EstimateValue(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    value: float | str | None = None
    unit: str
    status: Literal["available", "insufficient_data", "unavailable"] = "available"
    method: Literal["observed", "derived", "scenario", "index"]
    support: float = Field(0, ge=0, le=1)
    lower: float | None = None
    upper: float | None = None
    uncertainty: Literal["sensitivity_range", "sample_variation"] | None = None
    reason: str | None = None
    unavailable_cause: (
        Literal["missing_data", "outside_window", "not_applicable"] | None
    ) = None


class RaceEvent(BaseModel):
    id: str
    kind: str
    time_ms: int
    start_ms: int
    entry_id: str | None = None
    rival_entry_id: str | None = None
    severity: Literal["info", "watch", "warning"]
    classification: Literal["reported", "observed", "candidate"]
    title: str
    detail: str
    support: float = Field(ge=0, le=1)
    evidence: dict = Field(default_factory=dict)
    alternatives: list[str] = Field(default_factory=list)


class DriverEstimate(BaseModel):
    entry_id: str
    car_number: str
    ahead_entry_id: str | None = None
    metrics: dict[str, EstimateValue]
    series: list[dict] = Field(default_factory=list)
    braking_zones: list[dict] = Field(default_factory=list)
    pace_laps: list[dict] = Field(default_factory=list)


class RaceEstimateResponse(BaseModel):
    session_id: str
    version: str = MODEL_VERSION
    as_of_ms: int
    start_ms: int
    cache_hit: bool = False
    fingerprint: str
    assumptions: dict
    drivers: list[DriverEstimate]
    pairs: list[dict]
    events: list[RaceEvent]
    event_count: int
    events_truncated: bool
    conditions: dict
    warnings: list[str]
    interpretation: str = (
        "Support is evidence coverage, not a calibrated probability. Scenarios and indices are not measured tyre wear, temperature or accident probability."
    )


@dataclass
class RaceContext:
    driver_ids: dict[str, str] = field(default_factory=dict)
    intervals: list[dict] = field(default_factory=list)
    positions: list[dict] = field(default_factory=list)
    pits: list[dict] = field(default_factory=list)
    overtakes: list[dict] = field(default_factory=list)
