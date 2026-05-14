from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from modules.feature_metrics.domain.models import (
    AnalysisScope,
    FeatureMetricComponentValue,
    FeatureMetricEntry,
    FeatureMetricInputCoverage,
    MetricId,
)

DecisionSignalId = Literal["strongest_pace_driver", "most_consistent_driver", "recent_improver"]
DecisionSignalSeverity = Literal["info", "watch", "alert"]


class DecisionSignalDefinition(BaseModel):
    signal_id: DecisionSignalId
    version: str
    display_name: str
    description: str
    required_metrics: list[MetricId]
    supported_scopes: list[AnalysisScope]
    default_scope: AnalysisScope = "field"
    severity: DecisionSignalSeverity = "info"


class DecisionEngineStatus(BaseModel):
    engine_name: str
    status: str
    rule_count: int
    signal_definitions: list[DecisionSignalDefinition] = Field(default_factory=list)


class DecisionSignalRequest(BaseModel):
    signal_ids: list[DecisionSignalId] = Field(
        default_factory=lambda: ["strongest_pace_driver", "most_consistent_driver", "recent_improver"]
    )
    analysis_scope: AnalysisScope = "field"
    entry_ids: list[str] | None = None
    recent_laps: int = Field(default=5, ge=1, le=50)
    lap_from: int | None = Field(default=None, ge=1)
    lap_to: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_scope(self) -> "DecisionSignalRequest":
        if self.lap_from is not None and self.lap_to is not None and self.lap_from > self.lap_to:
            raise ValueError("lap_from must be less than or equal to lap_to")
        self.signal_ids = list(dict.fromkeys(self.signal_ids))
        if self.entry_ids is not None:
            self.entry_ids = list(dict.fromkeys(self.entry_ids))
            if self.analysis_scope == "field":
                self.analysis_scope = "explicit_entries"
        if self.analysis_scope in {"selected_entries", "explicit_entries"} and not self.entry_ids:
            raise ValueError("entry_ids are required for selected_entries or explicit_entries analysis scope")
        return self


class DecisionSignalEvidence(BaseModel):
    metric_id: MetricId
    metric_version: str
    value: float | None = None
    rank: int | None = None
    confidence: float
    comparison_scope: AnalysisScope
    components: dict[str, FeatureMetricComponentValue] = Field(default_factory=dict)


class DecisionSignal(BaseModel):
    signal_id: DecisionSignalId
    signal_version: str
    session_id: str
    primary_entry: FeatureMetricEntry
    title: str
    summary: str
    severity: DecisionSignalSeverity
    confidence: float
    evidence: DecisionSignalEvidence
    data_quality: FeatureMetricInputCoverage
    computed_at: datetime


class DecisionSignalListResponse(BaseModel):
    session_id: str
    analysis_scope: AnalysisScope
    computed_at: datetime
    signals: list[DecisionSignal] = Field(default_factory=list)
