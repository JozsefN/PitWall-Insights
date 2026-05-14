from __future__ import annotations

from modules.feature_metrics.domain.models import FeatureMetricsConfig

FEATURE_METRICS_CONFIG = FeatureMetricsConfig(
    config_version="feature_metrics_v1",
    recent_lap_count=5,
    minimum_laps_for_score=3,
    exclude_pit_laps=True,
    exclude_deleted_laps=True,
    require_accurate_laps=True,
    pace_story_threshold=75.0,
    consistency_story_threshold=75.0,
    lap_trend_story_threshold=70.0,
    lap_trend_minimum_improvement_ms=150.0,
    minimum_story_confidence=0.6,
)


def load_feature_metrics_config() -> FeatureMetricsConfig:
    return FEATURE_METRICS_CONFIG
