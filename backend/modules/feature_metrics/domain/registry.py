from __future__ import annotations

from modules.feature_metrics.domain.calculators.base import MetricCalculator
from modules.feature_metrics.domain.calculators.consistency_score import ConsistencyScoreCalculator
from modules.feature_metrics.domain.calculators.lap_trend import LapTrendCalculator
from modules.feature_metrics.domain.calculators.pace_rating import PaceRatingCalculator
from modules.feature_metrics.domain.models import FeatureMetricDefinition, MetricId

CALCULATORS: dict[MetricId, MetricCalculator] = {
    "pace_rating": PaceRatingCalculator(),
    "consistency_score": ConsistencyScoreCalculator(),
    "lap_trend": LapTrendCalculator(),
}

SUPPORTED_METRIC_IDS: tuple[MetricId, ...] = tuple(CALCULATORS.keys())


def get_calculators(metric_ids: list[MetricId]) -> list[MetricCalculator]:
    return [CALCULATORS[metric_id] for metric_id in metric_ids]


def get_metric_definitions(metric_ids: list[MetricId] | None = None) -> list[FeatureMetricDefinition]:
    selected_ids = metric_ids or list(SUPPORTED_METRIC_IDS)
    return [CALCULATORS[metric_id].definition for metric_id in selected_ids]
