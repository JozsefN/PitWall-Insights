"""Typed, versioned analytics contracts independent of HTTP and persistence."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

ANALYSIS_VERSION = "f1_analysis_v1"
GROUPS = (
    "laps",
    "stints",
    "speed",
    "controls",
    "powertrain",
    "position",
    "incidents",
    "racing",
    "conditions",
    "quality",
)


EVENT_KINDS = (
    "rapid_speed_drop",
    "non_pit_stop",
    "possible_incident",
    "reported_offtrack",
    "line_deviation",
    "race_control_driver_message",
)


class AnalysisOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    max_sample_gap_ms: int = Field(default=2000, ge=200, le=10000)
    full_throttle_pct: float = Field(default=95, ge=80, le=100)
    stopped_speed_kph: float = Field(default=5, ge=0, le=15)
    rapid_drop_kph: float = Field(default=100, ge=30, le=300)
    rapid_drop_window_ms: int = Field(default=2000, ge=250, le=5000)
    stopped_min_ms: int = Field(default=4000, ge=2000, le=30000)
    line_deviation_m: float = Field(default=15, ge=5, le=100)
    max_plausible_speed_kph: float = Field(default=450, ge=300, le=600)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_ids: list[str] | None = Field(default=None, min_length=1, max_length=64)
    metric_ids: list[str] | None = Field(default=None, min_length=1, max_length=250)
    groups: list[str] | None = Field(default=None, min_length=1, max_length=10)
    start_time_ms: int | None = Field(default=None, ge=0)
    end_time_ms: int | None = Field(default=None, ge=0)
    lap_from: int | None = Field(default=None, ge=1)
    lap_to: int | None = Field(default=None, ge=1)
    sample_interval_ms: int = Field(default=500, ge=100, le=5000)
    include_events: bool = True
    event_kinds: list[str] | None = Field(default=None, min_length=1, max_length=6)
    max_events: int = Field(default=500, ge=0, le=5000)
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)

    @model_validator(mode="after")
    def validate_window(self):
        if (
            self.start_time_ms is not None
            and self.end_time_ms is not None
            and self.start_time_ms >= self.end_time_ms
        ):
            raise ValueError("start_time_ms must be before end_time_ms")
        if (
            self.lap_from is not None
            and self.lap_to is not None
            and self.lap_from > self.lap_to
        ):
            raise ValueError("lap_from must not exceed lap_to")
        for name in ("entry_ids", "metric_ids", "groups", "event_kinds"):
            value = getattr(self, name)
            if value is not None:
                if any(not item.strip() for item in value):
                    raise ValueError(f"{name} must not contain blank values")
                setattr(self, name, sorted(set(value)))
        if self.groups is not None and set(self.groups) - set(GROUPS):
            raise ValueError("Unsupported analysis group")
        if self.event_kinds is not None and set(self.event_kinds) - set(EVENT_KINDS):
            raise ValueError("Unsupported event kind")
        if "max_sample_gap_ms" not in self.options.model_fields_set:
            self.options.max_sample_gap_ms = max(2000, 2 * self.sample_interval_ms)
        elif self.options.max_sample_gap_ms < self.sample_interval_ms:
            raise ValueError("max_sample_gap_ms must be at least sample_interval_ms")
        return self


class MetricDefinition(BaseModel):
    metric_id: str
    group: str
    unit: str
    description: str
    required_inputs: list[str]
    scope: Literal["entry", "session"] = "entry"
    interpretation: Literal["measured", "estimated", "inferred"] = "measured"
    version: str = ANALYSIS_VERSION


class MetricValue(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    metric_id: str
    entry_id: str | None = None
    value: JsonValue = None
    unit: str
    status: Literal["ok", "unavailable", "insufficient_data"]
    confidence: float = Field(ge=0, le=1)
    sample_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class AnalysisEvent(BaseModel):
    kind: str
    entry_id: str | None = None
    start_time_ms: int
    end_time_ms: int
    confidence: float = Field(ge=0, le=1)
    classification: Literal["observed", "candidate", "reported"]
    evidence: dict[str, JsonValue] = Field(default_factory=dict)


class AnalysisResponse(BaseModel):
    session_id: str
    version: str = ANALYSIS_VERSION
    computed_at: datetime
    start_time_ms: int
    end_time_ms: int
    sample_interval_ms: int
    cache_hit: bool = False
    data_fingerprint: str
    coverage: dict[str, JsonValue]
    metrics: list[MetricValue]
    events: list[AnalysisEvent] = Field(default_factory=list)
    total_event_count: int = 0
    events_truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


@dataclass
class EntryData:
    id: str
    car_number: str
    driver_name: str = ""
    grid_position: int | None = None
    laps: list[dict[str, Any]] = field(default_factory=list)
    stints: list[dict[str, Any]] = field(default_factory=list)
    car: list[dict[str, Any]] = field(default_factory=list)
    positions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AnalysisData:
    session_id: str
    start_ms: int
    end_ms: int
    source: str = "fastf1"
    entries: list[EntryData] = field(default_factory=list)
    weather: list[dict[str, Any]] = field(default_factory=list)
    track_status: list[dict[str, Any]] = field(default_factory=list)
    race_control: list[dict[str, Any]] = field(default_factory=list)
    reference: Any = None
    coverage: dict[str, Any] = field(default_factory=dict)


class AnalysisLimitError(ValueError):
    pass
