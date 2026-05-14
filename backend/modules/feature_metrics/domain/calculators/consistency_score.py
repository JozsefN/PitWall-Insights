from __future__ import annotations

from modules.feature_metrics.domain.calculators.base import MetricCalculator
from modules.feature_metrics.domain.calculators.shared import (
    DEFAULT_CORRECTIONS,
    apply_ranks,
    build_window,
    build_input_coverage,
    comparison_scope_for,
    confidence_for_sample_count,
    median_absolute_deviation_ms,
    normalize_lower_is_better,
    select_clean_laps,
    warnings_for_sample_count,
)
from modules.feature_metrics.domain.models import (
    FeatureMetricDataset,
    FeatureMetricDefinition,
    FeatureMetricDriverScore,
    FeatureMetricDriverScoreRequest,
    FeatureMetricLap,
    FeatureMetricsConfig,
)


class ConsistencyScoreCalculator(MetricCalculator):
    definition = FeatureMetricDefinition(
        metric_id="consistency_score",
        version="v1",
        display_name="Consistency Score",
        description="Field-relative clean-lap variance score using median absolute deviation.",
        supported_scopes=["field", "selected_entries", "explicit_entries", "lap_window"],
        required_inputs=["entries", "laps"],
        cost_level="cheap",
        output_kind="entry_score",
    )

    def compute(
        self,
        dataset: FeatureMetricDataset,
        request: FeatureMetricDriverScoreRequest,
        config: FeatureMetricsConfig,
    ) -> list[FeatureMetricDriverScore]:
        selected_laps_by_entry = {
            entry.id: select_clean_laps(
                dataset.laps_by_entry_id.get(entry.id, []),
                request,
                config,
            )
            for entry in dataset.entries
        }
        variation_by_entry: dict[str, float] = {}
        median_by_entry: dict[str, float] = {}
        for entry_id, laps in selected_laps_by_entry.items():
            variation_ms, median_ms = median_absolute_deviation_ms(laps)
            if variation_ms is not None:
                variation_by_entry[entry_id] = variation_ms
            if median_ms is not None:
                median_by_entry[entry_id] = median_ms

        score_by_entry = normalize_lower_is_better(variation_by_entry)

        scores = [
            self._score_entry(
                entry=entry,
                laps=selected_laps_by_entry.get(entry.id, []),
                variation_ms=variation_by_entry.get(entry.id),
                median_ms=median_by_entry.get(entry.id),
                normalized_score=score_by_entry.get(entry.id),
                request=request,
                config=config,
                input_coverage=build_input_coverage(dataset, entry.id),
            )
            for entry in dataset.entries
        ]
        return apply_ranks(scores)

    def _score_entry(
        self,
        *,
        entry,
        laps: list[FeatureMetricLap],
        variation_ms: float | None,
        median_ms: float | None,
        normalized_score: float | None,
        request: FeatureMetricDriverScoreRequest,
        config: FeatureMetricsConfig,
        input_coverage,
    ) -> FeatureMetricDriverScore:
        sample_count = len(laps)

        return FeatureMetricDriverScore(
            metric_id=self.definition.metric_id,
            metric_version=self.definition.version,
            analysis_scope=request.analysis_scope,
            comparison_scope=comparison_scope_for(request),
            entry=entry,
            value=normalized_score,
            rank=None,
            confidence=confidence_for_sample_count(sample_count, config),
            sample_count=sample_count,
            window=build_window(laps, request),
            components={
                "median_absolute_deviation_ms": round(variation_ms, 3) if variation_ms is not None else None,
                "median_lap_time_ms": round(median_ms, 3) if median_ms is not None else None,
                "normalization": "field_relative_low_variance_recent_clean_laps",
            },
            corrections=DEFAULT_CORRECTIONS.copy(),
            input_coverage=input_coverage,
            warnings=warnings_for_sample_count(sample_count, config),
        )
