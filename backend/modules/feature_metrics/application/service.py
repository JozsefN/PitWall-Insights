from __future__ import annotations

from datetime import datetime, timezone

from modules.feature_metrics.domain.models import (
    AnalysisScope,
    FeatureMetricDriverScoreRequest,
    FeatureMetricDriverScoresResponse,
    FeatureMetricsConfig,
    FeatureMetricsStatus,
    MetricId,
)
from modules.feature_metrics.application.planner import build_feature_metric_plan
from modules.feature_metrics.domain.registry import SUPPORTED_METRIC_IDS, get_metric_definitions
from modules.feature_metrics.infrastructure.config import load_feature_metrics_config
from modules.feature_metrics.infrastructure.input_provider import FeatureMetricInputProvider


class FeatureMetricsService:
    def __init__(
        self,
        input_provider: FeatureMetricInputProvider | None = None,
        config: FeatureMetricsConfig | None = None,
    ) -> None:
        self.input_provider = input_provider
        self.config = config or load_feature_metrics_config()

    def get_status(self) -> FeatureMetricsStatus:
        return FeatureMetricsStatus(
            metrics_set_name="core_session_metrics",
            status="ready",
            computed_fields_available=len(SUPPORTED_METRIC_IDS),
            api_metrics_available=list(SUPPORTED_METRIC_IDS),
            config_version=self.config.config_version,
            calculator_definitions=get_metric_definitions(),
        )

    def compute_driver_scores(
        self,
        session_id: str,
        *,
        metric_ids: list[MetricId] | None = None,
        analysis_scope: AnalysisScope = "field",
        entry_ids: list[str] | None = None,
        recent_laps: int | None = None,
        lap_from: int | None = None,
        lap_to: int | None = None,
    ) -> FeatureMetricDriverScoresResponse | None:
        if self.input_provider is None:
            raise RuntimeError("FeatureMetricInputProvider is required for metric computation")

        request = FeatureMetricDriverScoreRequest(
            metric_ids=metric_ids or list(SUPPORTED_METRIC_IDS),
            analysis_scope=analysis_scope,
            entry_ids=entry_ids,
            recent_laps=recent_laps or self.config.recent_lap_count,
            lap_from=lap_from,
            lap_to=lap_to,
        )
        plan = build_feature_metric_plan(request)
        dataset = self.input_provider.load_dataset(
            session_id,
            request=plan.request,
            required_inputs=plan.required_inputs,
        )
        if dataset is None:
            return None

        metrics = []
        for calculator in plan.calculators:
            metrics.extend(calculator.compute(dataset, plan.request, self.config))

        return FeatureMetricDriverScoresResponse(
            session_id=session_id,
            analysis_scope=plan.request.analysis_scope,
            comparison_scope=plan.request.analysis_scope,
            computed_at=datetime.now(timezone.utc),
            config_version=self.config.config_version,
            metric_definitions=get_metric_definitions(plan.request.metric_ids),
            input_coverage=self.input_provider.summarize_coverage(dataset),
            metrics=metrics,
        )
