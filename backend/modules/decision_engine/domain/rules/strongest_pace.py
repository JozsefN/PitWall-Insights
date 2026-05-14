from __future__ import annotations

from modules.decision_engine.domain.models import DecisionSignal, DecisionSignalDefinition
from modules.decision_engine.domain.rules.base import DecisionRule
from modules.decision_engine.domain.rules.shared import build_signal, driver_label, top_score
from modules.feature_metrics.domain.models import FeatureMetricDriverScoresResponse, FeatureMetricsConfig


class StrongestPaceRule(DecisionRule):
    definition = DecisionSignalDefinition(
        signal_id="strongest_pace_driver",
        version="v1",
        display_name="Strongest Pace Driver",
        description="Highlights the driver with the strongest pace rating in the requested scope.",
        required_metrics=["pace_rating"],
        supported_scopes=["field", "explicit_entries", "selected_entries"],
        default_scope="field",
        severity="info",
    )

    def evaluate(
        self,
        metrics: FeatureMetricDriverScoresResponse,
        config: FeatureMetricsConfig,
    ) -> DecisionSignal | None:
        score = top_score(metrics, "pace_rating")
        if score is None or score.value is None:
            return None
        if score.confidence < config.minimum_story_confidence or score.value < config.pace_story_threshold:
            return None

        label = driver_label(score)
        return build_signal(
            definition=self.definition,
            metrics=metrics,
            score=score,
            title="Strongest pace rating",
            summary=f"{label} has the strongest pace rating over the current clean-lap window.",
        )
