from __future__ import annotations

from dataclasses import dataclass

from modules.feature_metrics.domain.calculators.base import MetricCalculator
from modules.feature_metrics.domain.models import FeatureMetricDriverScoreRequest, MetricInputKind
from modules.feature_metrics.domain.registry import get_calculators


@dataclass(frozen=True)
class FeatureMetricPlan:
    request: FeatureMetricDriverScoreRequest
    calculators: list[MetricCalculator]
    required_inputs: list[MetricInputKind]


def build_feature_metric_plan(request: FeatureMetricDriverScoreRequest) -> FeatureMetricPlan:
    calculators = get_calculators(request.metric_ids)
    required_inputs: list[MetricInputKind] = []

    for calculator in calculators:
        definition = calculator.definition
        if request.analysis_scope not in definition.supported_scopes:
            raise ValueError(
                f'Metric "{definition.metric_id}" does not support analysis scope "{request.analysis_scope}".'
            )
        for input_kind in definition.required_inputs:
            if input_kind not in required_inputs:
                required_inputs.append(input_kind)

    return FeatureMetricPlan(
        request=request,
        calculators=calculators,
        required_inputs=required_inputs,
    )
