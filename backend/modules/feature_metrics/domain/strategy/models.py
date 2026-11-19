"""Deterministic, event-time strategy contracts. Percentages never stand in for confidence."""

from datetime import datetime
from typing import Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
    AwareDatetime,
)
from modules.feature_metrics.domain.analysis.models import AnalysisData

STRATEGY_VERSION = "strategy_foundation_v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Bounds(StrictModel):
    lower: float
    upper: float
    meaning: Literal[
        "sensitivity_range",
        "sampling_band",
        "credible_interval_95",
        "conditional_prediction_band",
        "coefficient_interval_95",
    ]

    @model_validator(mode="after")
    def ordered(self):
        if self.lower > self.upper:
            raise ValueError("lower must not exceed upper")
        return self


class StrategyValue(StrictModel):
    metric_id: str
    entry_id: str | None = None
    rival_entry_id: str | None = None
    value: JsonValue = None
    unit: str
    status: Literal["observed", "derived", "estimated", "assumed", "unavailable"]
    sample_count: int = Field(default=0, ge=0)
    bounds: Bounds | None = None
    as_of_ms: int
    support: dict[str, JsonValue] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class Zone(StrictModel):
    zone_id: str = Field(min_length=1, max_length=80)
    kind: Literal[
        "racing_surface", "pit_lane", "recovery", "gravel", "runoff", "marshal_sector"
    ]
    sector_number: int | None = Field(default=None, ge=1, le=200)
    polygon_m: list[tuple[float, float]] = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def polygon(self):
        from .spatial import polygon_area

        if (self.kind == "marshal_sector") != (self.sector_number is not None):
            raise ValueError("Only marshal sectors require a sector number")
        if abs(polygon_area(self.polygon_m)) < 1:
            raise ValueError(
                "Zone polygon must have nonzero area of at least one square metre"
            )
        return self


class TrackProfile(StrictModel):
    circuit_key: str = Field(min_length=1, max_length=120)
    coordinate_frame: str = Field(min_length=1, max_length=120)
    source_uri: str = Field(min_length=1, max_length=500)
    source_license: str | None = Field(default=None, min_length=1, max_length=180)
    valid_season_from: int = Field(ge=2020, le=2100)
    valid_season_to: int = Field(ge=2020, le=2100)
    north_angle_xy_deg: float | None = Field(default=None, ge=-360, le=360)
    alignment_error_deg: float | None = Field(default=None, ge=0, le=180)
    position_error_m: float = Field(default=15, ge=5, le=200)
    circuit_length_m: float | None = Field(default=None, gt=0, le=30000)
    zones: list[Zone] = Field(default_factory=list, max_length=100)
    recovery_points_m: list[tuple[float, float]] = Field(
        default_factory=list, max_length=300
    )
    pit_entry_progress_pct: float | None = Field(default=None, ge=0, lt=100)

    @model_validator(mode="after")
    def valid(self):
        if self.valid_season_from > self.valid_season_to:
            raise ValueError("Track profile season range is inverted")
        if self.north_angle_xy_deg is not None and self.alignment_error_deg is None:
            raise ValueError("North alignment requires an error bound")
        return self


class PitObservation(StrictModel):
    entry_id: str
    lap_number: int = Field(ge=1)
    event_time_ms: int = Field(ge=0)
    known_at_ms: int = Field(ge=0)
    lane_duration_s: float | None = Field(default=None, gt=0, le=600)
    stationary_duration_s: float | None = Field(default=None, gt=0, le=600)
    source_uri: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def valid(self):
        if self.known_at_ms < self.event_time_ms:
            raise ValueError("Pit report cannot be known before its event")
        if (
            self.stationary_duration_s is not None
            and self.lane_duration_s is not None
            and self.stationary_duration_s > self.lane_duration_s
        ):
            raise ValueError("Stationary time cannot exceed pit-lane duration")
        return self


class TyreCurve(StrictModel):
    compound: str = Field(min_length=1, max_length=30)
    base_delta_s: float = Field(ge=-10, le=30)
    degradation_s_per_lap: float = Field(ge=-0.2, le=2)
    quadratic_s_per_lap2: float = Field(default=0, ge=0, le=0.2)
    warmup_deltas_s: list[float] = Field(default_factory=list, max_length=5)
    max_valid_age_laps: int = Field(ge=1, le=100)
    uncertainty_s_per_lap: float = Field(ge=0, le=10)
    provenance: Literal["measured_calibration", "user_scenario"]
    source_uri: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def warmup_range(self):
        if any(not -10 <= value <= 30 for value in self.warmup_deltas_s):
            raise ValueError("Warmup deltas must be between -10 and 30 seconds")
        return self


class TyreSet(StrictModel):
    set_id: str = Field(min_length=1, max_length=80)
    compound: str
    initial_age_laps: int = Field(default=0, ge=0, le=100)


class PitLossModel(StrictModel):
    green_s: float = Field(gt=0, le=100)
    vsc_s: float | None = Field(default=None, gt=0, le=100)
    sc_s: float | None = Field(default=None, gt=0, le=100)
    uncertainty_s: float = Field(ge=0, le=30)
    provenance: Literal["measured_calibration", "user_scenario"]
    source_uri: str = Field(min_length=1, max_length=500)


class RuleProfile(StrictModel):
    profile_id: str
    season_year: int = Field(ge=2020, le=2100)
    minimum_distinct_compounds: int = Field(ge=1, le=3)
    minimum_stops: int = Field(default=0, ge=0, le=5)
    source_uri: str = Field(min_length=1, max_length=500)


class IncidentHistory(StrictModel):
    observation_id: str
    incident_id: str
    circuit_key: str
    observed_at_utc: AwareDatetime
    stopped: bool
    surface: Literal["on_track", "off_track", "unknown"]
    recovery_access: Literal["near", "far", "unknown"]
    terrain: Literal["gravel", "runoff", "recovery"] | None = None
    elapsed_stop_bin: Literal["4_10", "10_30", "30_plus"] = "4_10"
    horizon_s: int = Field(default=120, ge=30, le=600)
    outcome: Literal["sc", "vsc", "red", "none"]
    sc_occurred: bool | None = None
    vsc_occurred: bool | None = None
    red_occurred: bool | None = None
    source_uri: str = Field(min_length=1, max_length=500)


class StrategyContext(StrictModel):
    known_at_ms: int = Field(ge=0)
    source_note: str = Field(min_length=1, max_length=1000)
    track: TrackProfile | None = None
    pit_observations: list[PitObservation] = Field(default_factory=list, max_length=200)
    tyre_curves: list[TyreCurve] = Field(default_factory=list, max_length=8)
    tyre_inventory: dict[str, list[TyreSet]] = Field(default_factory=dict)
    pit_loss: PitLossModel | None = None
    rules: RuleProfile | None = None
    incident_history: list[IncidentHistory] = Field(
        default_factory=list, max_length=5000
    )

    @model_validator(mode="after")
    def unique(self):
        if len({curve.compound for curve in self.tyre_curves}) != len(self.tyre_curves):
            raise ValueError("Duplicate tyre compound curves")
        if len({row.observation_id for row in self.incident_history}) != len(
            self.incident_history
        ):
            raise ValueError("Duplicate calibration observations")
        if len(
            {(row.incident_id, row.elapsed_stop_bin) for row in self.incident_history}
        ) != len(self.incident_history):
            raise ValueError("An incident may contribute once per elapsed-time cohort")
        if (
            sum(len(zone.polygon_m) for zone in self.track.zones) > 10000
            if self.track
            else False
        ):
            raise ValueError("Track context permits at most 10000 polygon vertices")
        if len(self.tyre_inventory) > 64 or any(
            len(sets) > 12 or len({s.set_id for s in sets}) != len(sets)
            for sets in self.tyre_inventory.values()
        ):
            raise ValueError(
                "Inventory permits at most 64 entries, 12 uniquely identified sets each"
            )
        return self


class StrategyRequest(StrictModel):
    mode: Literal["race", "counterfactual"] = "race"
    as_of_ms: int = Field(ge=0)
    focus_entry_id: str
    rival_entry_ids: list[str] | None = Field(default=None, max_length=30)
    context_id: str | None = None
    telemetry_lookback_ms: int = Field(default=180000, ge=30000, le=900000)
    sample_interval_ms: int = Field(default=500, ge=100, le=2000)
    remaining_laps: int | None = Field(default=None, ge=1, le=80)
    max_stops: int = Field(default=2, ge=0, le=2)
    race_horizon_s: int = Field(default=120, ge=30, le=600)
    rival_headway_target_s: float = Field(default=1, ge=0, le=10)
    min_probability_cohort: int = Field(default=30, ge=10, le=500)

    @model_validator(mode="after")
    def unique(self):
        if self.rival_entry_ids is not None:
            self.rival_entry_ids = sorted(
                set(self.rival_entry_ids) - {self.focus_entry_id}
            )
        return self


class PlanStop(StrictModel):
    after_laps: int
    set_id: str
    compound: str


class StrategyPlan(StrictModel):
    stops: list[PlanStop]
    projected_time_s: float
    sensitivity: Bounds
    gain_vs_stay_out_s: float | None = None
    satisfies_configured_rules: bool
    assumptions: list[str] = Field(default_factory=list)


class StrategyResponse(StrictModel):
    session_id: str
    version: str = STRATEGY_VERSION
    as_of_ms: int
    context_id: str | None
    data_fingerprint: str
    computed_at: datetime
    cache_hit: bool = False
    values: list[StrategyValue]
    pair_series: dict[str, list[dict[str, JsonValue]]] = Field(default_factory=dict)
    events: list[dict[str, JsonValue]] = Field(default_factory=list)
    models: dict[str, JsonValue] = Field(default_factory=dict)
    plans: list[StrategyPlan] = Field(default_factory=list)
    best_modeled_plan: StrategyPlan | None = None
    recommendation_status: str
    readiness: dict[str, JsonValue]
    warnings: list[str]
