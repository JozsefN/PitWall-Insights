from __future__ import annotations

from datetime import datetime, timezone

from modules.decision_engine.domain.models import (
    DecisionSignal,
    DecisionSignalDefinition,
    DecisionSignalEvidence,
)
from modules.feature_metrics.domain.models import (
    FeatureMetricDriverScore,
    FeatureMetricDriverScoresResponse,
)


def driver_label(score: FeatureMetricDriverScore) -> str:
    return score.entry.driver_abbreviation or score.entry.driver_name or f"#{score.entry.car_number}"


def top_score(
    metrics: FeatureMetricDriverScoresResponse,
    metric_id: str,
) -> FeatureMetricDriverScore | None:
    candidates = [
        score
        for score in metrics.metrics
        if score.metric_id == metric_id and score.value is not None
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda score: (score.rank or 9999, -score.confidence))[0]


def build_signal(
    *,
    definition: DecisionSignalDefinition,
    metrics: FeatureMetricDriverScoresResponse,
    score: FeatureMetricDriverScore,
    title: str,
    summary: str,
) -> DecisionSignal:
    return DecisionSignal(
        signal_id=definition.signal_id,
        signal_version=definition.version,
        session_id=metrics.session_id,
        primary_entry=score.entry,
        title=title,
        summary=summary,
        severity=definition.severity,
        confidence=score.confidence,
        evidence=DecisionSignalEvidence(
            metric_id=score.metric_id,
            metric_version=score.metric_version,
            value=score.value,
            rank=score.rank,
            confidence=score.confidence,
            comparison_scope=score.comparison_scope,
            components=score.components,
        ),
        data_quality=score.input_coverage,
        computed_at=datetime.now(timezone.utc),
    )
