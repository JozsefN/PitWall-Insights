from __future__ import annotations

from modules.decision_engine.domain.models import DecisionSignal, DecisionSignalDefinition
from modules.decision_engine.domain.rules.base import DecisionRule
from modules.decision_engine.domain.rules.shared import build_signal, driver_label, top_score
from modules.feature_metrics.domain.models import FeatureMetricDriverScoresResponse, FeatureMetricsConfig


class MostConsistentRule(DecisionRule):
    definition = DecisionSignalDefinition(
        signal_id="most_consistent_driver",
        version="v1",
        display_name="Most Consistent Driver",
        description="Highlights the driver with the best clean-lap consistency score.",
        required_metrics=["consistency_score"],
        supported_scopes=["field", "explicit_entries", "selected_entries"],
        default_scope="field",
        severity="info",
    )

    def evaluate(
        self,
        metrics: FeatureMetricDriverScoresResponse,
        config: FeatureMetricsConfig,
    ) -> DecisionSignal | None:
        score = top_score(metrics, "consistency_score")
        if score is None or score.value is None:
            return None
        if score.confidence < config.minimum_story_confidence or score.value < config.consistency_story_threshold:
            return None

        label = driver_label(score)
        return build_signal(
            definition=self.definition,
            metrics=metrics,
            score=score,
            title="Most consistent driver",
            summary=f"{label} is the most consistent driver in the current clean-lap window.",
        )
