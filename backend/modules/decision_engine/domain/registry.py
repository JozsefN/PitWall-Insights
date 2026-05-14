from __future__ import annotations

from modules.decision_engine.domain.models import DecisionSignalDefinition, DecisionSignalId
from modules.decision_engine.domain.rules.base import DecisionRule
from modules.decision_engine.domain.rules.most_consistent import MostConsistentRule
from modules.decision_engine.domain.rules.recent_improver import RecentImproverRule
from modules.decision_engine.domain.rules.strongest_pace import StrongestPaceRule
from modules.feature_metrics.domain.models import MetricId

RULES: dict[DecisionSignalId, DecisionRule] = {
    "strongest_pace_driver": StrongestPaceRule(),
    "most_consistent_driver": MostConsistentRule(),
    "recent_improver": RecentImproverRule(),
}

SUPPORTED_SIGNAL_IDS: tuple[DecisionSignalId, ...] = tuple(RULES.keys())


def get_rules(signal_ids: list[DecisionSignalId]) -> list[DecisionRule]:
    return [RULES[signal_id] for signal_id in signal_ids]


def get_signal_definitions(signal_ids: list[DecisionSignalId] | None = None) -> list[DecisionSignalDefinition]:
    selected_ids = signal_ids or list(SUPPORTED_SIGNAL_IDS)
    return [RULES[signal_id].definition for signal_id in selected_ids]


def required_metrics_for(signal_ids: list[DecisionSignalId]) -> list[MetricId]:
    metric_ids: list[MetricId] = []
    for rule in get_rules(signal_ids):
        for metric_id in rule.definition.required_metrics:
            if metric_id not in metric_ids:
                metric_ids.append(metric_id)
    return metric_ids
