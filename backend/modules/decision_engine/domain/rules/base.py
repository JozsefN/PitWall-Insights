from __future__ import annotations

from abc import ABC, abstractmethod

from modules.decision_engine.domain.models import DecisionSignal, DecisionSignalDefinition
from modules.feature_metrics.domain.models import (
    FeatureMetricDriverScoresResponse,
    FeatureMetricsConfig,
)


class DecisionRule(ABC):
    definition: DecisionSignalDefinition

    @abstractmethod
    def evaluate(
        self,
        metrics: FeatureMetricDriverScoresResponse,
        config: FeatureMetricsConfig,
    ) -> DecisionSignal | None:
        raise NotImplementedError
