from __future__ import annotations

from abc import ABC, abstractmethod

from modules.feature_metrics.domain.models import (
    FeatureMetricDataset,
    FeatureMetricDefinition,
    FeatureMetricDriverScore,
    FeatureMetricDriverScoreRequest,
    FeatureMetricsConfig,
)


class MetricCalculator(ABC):
    definition: FeatureMetricDefinition

    @abstractmethod
    def compute(
        self,
        dataset: FeatureMetricDataset,
        request: FeatureMetricDriverScoreRequest,
        config: FeatureMetricsConfig,
    ) -> list[FeatureMetricDriverScore]:
        raise NotImplementedError
