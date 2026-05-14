from __future__ import annotations

from modules.feature_metrics.domain.calculators.base import MetricCalculator
from modules.feature_metrics.domain.calculators.shared import (
    DEFAULT_CORRECTIONS,
    apply_ranks,
    build_window,
    build_input_coverage,
    comparison_scope_for,
    confidence_for_sample_count,
    median_lap_time_ms,
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


class PaceRatingCalculator(MetricCalculator):
    definition = FeatureMetricDefinition(
        metric_id="pace_rating",
        version="v1",
        display_name="Pace Rating",
        description="Field-relative recent clean-lap pace score.",
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
        median_by_entry = {
            entry_id: median_ms
            for entry_id, laps in selected_laps_by_entry.items()
            if (median_ms := median_lap_time_ms(laps)) is not None
        }
        score_by_entry = normalize_lower_is_better(median_by_entry)
        best_median = min(median_by_entry.values()) if median_by_entry else None

        scores = [
            self._score_entry(
                entry=entry,
                laps=selected_laps_by_entry.get(entry.id, []),
                median_ms=median_by_entry.get(entry.id),
                best_median=best_median,
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
        median_ms: float | None,
        best_median: float | None,
        normalized_score: float | None,
        request: FeatureMetricDriverScoreRequest,
        config: FeatureMetricsConfig,
        input_coverage,
    ) -> FeatureMetricDriverScore:
        sample_count = len(laps)
        delta_to_best = (
            round(median_ms - best_median, 3)
            if median_ms is not None and best_median is not None
            else None
        )

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
                "median_lap_time_ms": round(median_ms, 3) if median_ms is not None else None,
                "delta_to_best_ms": delta_to_best,
                "normalization": "field_relative_recent_clean_laps",
            },
            corrections=DEFAULT_CORRECTIONS.copy(),
            input_coverage=input_coverage,
            warnings=warnings_for_sample_count(sample_count, config),
        )
