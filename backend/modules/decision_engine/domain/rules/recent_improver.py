from __future__ import annotations

from modules.decision_engine.domain.models import DecisionSignal, DecisionSignalDefinition
from modules.decision_engine.domain.rules.base import DecisionRule
from modules.decision_engine.domain.rules.shared import build_signal, driver_label, top_score
from modules.feature_metrics.domain.models import FeatureMetricDriverScoresResponse, FeatureMetricsConfig


class RecentImproverRule(DecisionRule):
    definition = DecisionSignalDefinition(
        signal_id="recent_improver",
        version="v1",
        display_name="Recent Improver",
        description="Highlights the driver with the strongest recent lap-time improvement.",
        required_metrics=["lap_trend"],
        supported_scopes=["field", "explicit_entries", "selected_entries"],
        default_scope="field",
        severity="watch",
    )

    def evaluate(
        self,
        metrics: FeatureMetricDriverScoresResponse,
        config: FeatureMetricsConfig,
    ) -> DecisionSignal | None:
        score = top_score(metrics, "lap_trend")
        if score is None or score.value is None:
            return None

        improvement_ms = score.components.get("improvement_ms")
        if not isinstance(improvement_ms, (int, float)):
            return None
        if improvement_ms < config.lap_trend_minimum_improvement_ms:
            return None
        if score.confidence < config.minimum_story_confidence or score.value < config.lap_trend_story_threshold:
            return None

        label = driver_label(score)
        return build_signal(
            definition=self.definition,
            metrics=metrics,
            score=score,
            title="Recent pace improver",
            summary=f"{label} improved by {improvement_ms / 1000:.2f}s versus the previous clean-lap window.",
        )
