from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


MetricId = Literal["pace_rating", "consistency_score", "lap_trend"]
AnalysisScope = Literal["field", "selected_entries", "explicit_entries", "pair", "lap_window", "stint"]
CorrectionStatus = Literal["not_applied", "partial", "applied", "not_available"]
MetricInputKind = Literal[
    "session",
    "entries",
    "laps",
    "stints",
    "car_telemetry",
    "position_telemetry",
    "race_control",
    "weather",
]
MetricCostLevel = Literal["cheap", "moderate", "expensive"]
MetricOutputKind = Literal["entry_score", "entry_delta", "entry_series", "pair_score", "session_signal"]


class FeatureMetricsConfig(BaseModel):
    config_version: str = "feature_metrics_v1"
    recent_lap_count: int = Field(default=5, ge=1, le=50)
    minimum_laps_for_score: int = Field(default=3, ge=1, le=20)
    exclude_pit_laps: bool = True
    exclude_deleted_laps: bool = True
    require_accurate_laps: bool = True
    pace_story_threshold: float = Field(default=75.0, ge=0.0, le=100.0)
    consistency_story_threshold: float = Field(default=75.0, ge=0.0, le=100.0)
    lap_trend_story_threshold: float = Field(default=70.0, ge=0.0, le=100.0)
    lap_trend_minimum_improvement_ms: float = Field(default=150.0, ge=0.0)
    minimum_story_confidence: float = Field(default=0.6, ge=0.0, le=1.0)


class FeatureMetricsStatus(BaseModel):
    metrics_set_name: str
    status: str
    computed_fields_available: int
    api_metrics_available: list[MetricId] = Field(default_factory=list)
    config_version: str | None = None
    calculator_definitions: list["FeatureMetricDefinition"] = Field(default_factory=list)


class FeatureMetricDefinition(BaseModel):
    metric_id: MetricId
    version: str
    display_name: str
    description: str
    supported_scopes: list[AnalysisScope]
    required_inputs: list[MetricInputKind]
    cost_level: MetricCostLevel
    output_kind: MetricOutputKind
    api_visible: bool = True


class FeatureMetricDriverScoreRequest(BaseModel):
    metric_ids: list[MetricId] = Field(default_factory=lambda: ["pace_rating", "consistency_score", "lap_trend"])
    analysis_scope: AnalysisScope = "field"
    entry_ids: list[str] | None = None
    recent_laps: int = Field(default=5, ge=1, le=50)
    lap_from: int | None = Field(default=None, ge=1)
    lap_to: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_lap_range(self) -> "FeatureMetricDriverScoreRequest":
        if self.lap_from is not None and self.lap_to is not None and self.lap_from > self.lap_to:
            raise ValueError("lap_from must be less than or equal to lap_to")
        self.metric_ids = list(dict.fromkeys(self.metric_ids))
        if self.entry_ids is not None:
            self.entry_ids = list(dict.fromkeys(self.entry_ids))
            if self.analysis_scope == "field":
                self.analysis_scope = "explicit_entries"
        if self.analysis_scope in {"selected_entries", "explicit_entries"} and not self.entry_ids:
            raise ValueError("entry_ids are required for selected_entries or explicit_entries analysis scope")
        return self


class FeatureMetricEntry(BaseModel):
    id: str
    car_number: str
    driver_id: str
    driver_number: str | None = None
    driver_abbreviation: str | None = None
    driver_name: str | None = None
    team_id: str | None = None
    team_name: str | None = None
    team_color: str | None = None


class FeatureMetricLap(BaseModel):
    id: str
    entry_id: str
    lap_number: int
    lap_time_ms: int | None = None
    lap_start_time_ms: int | None = None
    lap_end_time_ms: int | None = None
    pit_out_time_ms: int | None = None
    pit_in_time_ms: int | None = None
    sector_1_time_ms: int | None = None
    sector_2_time_ms: int | None = None
    sector_3_time_ms: int | None = None
    compound: str | None = None
    tyre_life: int | None = None
    track_status: str | None = None
    is_deleted: bool
    is_generated: bool
    is_accurate: bool


class FeatureMetricDataset(BaseModel):
    session_id: str
    analysis_scope: AnalysisScope
    entries: list[FeatureMetricEntry] = Field(default_factory=list)
    laps_by_entry_id: dict[str, list[FeatureMetricLap]] = Field(default_factory=dict)
    loaded_inputs: list[MetricInputKind] = Field(default_factory=list)
    missing_inputs: list[MetricInputKind] = Field(default_factory=list)


class FeatureMetricInputCoverage(BaseModel):
    loaded_inputs: list[MetricInputKind] = Field(default_factory=list)
    missing_inputs: list[MetricInputKind] = Field(default_factory=list)
    entry_count: int = 0
    lap_count: int = 0


class FeatureMetricWindow(BaseModel):
    lap_from: int | None = None
    lap_to: int | None = None
    recent_laps: int
    lap_numbers: list[int] = Field(default_factory=list)


FeatureMetricComponentValue = float | int | str | bool | list[int] | list[float] | list[str] | None


class FeatureMetricDriverScore(BaseModel):
    metric_id: MetricId
    metric_version: str
    analysis_scope: AnalysisScope
    comparison_scope: AnalysisScope
    entry: FeatureMetricEntry
    value: float | None = Field(default=None, ge=0.0, le=100.0)
    rank: int | None = Field(default=None, ge=1)
    confidence: float = Field(ge=0.0, le=1.0)
    sample_count: int = Field(ge=0)
    window: FeatureMetricWindow
    components: dict[str, FeatureMetricComponentValue] = Field(default_factory=dict)
    corrections: dict[str, CorrectionStatus] = Field(default_factory=dict)
    input_coverage: FeatureMetricInputCoverage
    warnings: list[str] = Field(default_factory=list)


class FeatureMetricDriverScoresResponse(BaseModel):
    session_id: str
    analysis_scope: AnalysisScope
    comparison_scope: AnalysisScope
    computed_at: datetime
    config_version: str
    metric_definitions: list[FeatureMetricDefinition] = Field(default_factory=list)
    input_coverage: FeatureMetricInputCoverage
    metrics: list[FeatureMetricDriverScore] = Field(default_factory=list)
