from __future__ import annotations

from modules.feature_metrics.domain.calculators.base import MetricCalculator
from modules.feature_metrics.domain.calculators.shared import (
    DEFAULT_CORRECTIONS,
    apply_ranks,
    build_input_coverage,
    build_window,
    comparison_scope_for,
    confidence_for_sample_count,
    median_lap_time_ms,
    normalize_higher_is_better,
    select_clean_laps,
    select_previous_clean_laps,
)
from modules.feature_metrics.domain.models import (
    FeatureMetricDataset,
    FeatureMetricDefinition,
    FeatureMetricDriverScore,
    FeatureMetricDriverScoreRequest,
    FeatureMetricLap,
    FeatureMetricsConfig,
)


class LapTrendCalculator(MetricCalculator):
    definition = FeatureMetricDefinition(
        metric_id="lap_trend",
        version="v1",
        display_name="Lap Trend",
        description="Recent clean-lap improvement versus the previous comparable lap window.",
        supported_scopes=["field", "selected_entries", "explicit_entries", "lap_window"],
        required_inputs=["entries", "laps"],
        cost_level="cheap",
        output_kind="entry_delta",
    )

    def compute(
        self,
        dataset: FeatureMetricDataset,
        request: FeatureMetricDriverScoreRequest,
        config: FeatureMetricsConfig,
    ) -> list[FeatureMetricDriverScore]:
        windows_by_entry: dict[str, tuple[list[FeatureMetricLap], list[FeatureMetricLap]]] = {}
        improvement_by_entry: dict[str, float] = {}
        medians_by_entry: dict[str, tuple[float | None, float | None]] = {}

        for entry in dataset.entries:
            all_laps = dataset.laps_by_entry_id.get(entry.id, [])
            recent_laps = select_clean_laps(all_laps, request, config)
            previous_laps = select_previous_clean_laps(all_laps, recent_laps, request, config)
            recent_median = median_lap_time_ms(recent_laps)
            previous_median = median_lap_time_ms(previous_laps)
            windows_by_entry[entry.id] = (recent_laps, previous_laps)
            medians_by_entry[entry.id] = (recent_median, previous_median)

            if recent_median is not None and previous_median is not None:
                improvement_by_entry[entry.id] = previous_median - recent_median

        score_by_entry = normalize_higher_is_better(improvement_by_entry)

        scores = [
            self._score_entry(
                entry=entry,
                recent_laps=windows_by_entry.get(entry.id, ([], []))[0],
                previous_laps=windows_by_entry.get(entry.id, ([], []))[1],
                recent_median=medians_by_entry.get(entry.id, (None, None))[0],
                previous_median=medians_by_entry.get(entry.id, (None, None))[1],
                improvement_ms=improvement_by_entry.get(entry.id),
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
        recent_laps: list[FeatureMetricLap],
        previous_laps: list[FeatureMetricLap],
        recent_median: float | None,
        previous_median: float | None,
        improvement_ms: float | None,
        normalized_score: float | None,
        request: FeatureMetricDriverScoreRequest,
        config: FeatureMetricsConfig,
        input_coverage,
    ) -> FeatureMetricDriverScore:
        sample_count = len(recent_laps)
        confidence_window_count = min(len(recent_laps), len(previous_laps))
        warnings = []
        if len(recent_laps) < config.minimum_laps_for_score:
            warnings.append("Recent lap window has too few usable clean laps; confidence is reduced.")
        if len(previous_laps) < config.minimum_laps_for_score:
            warnings.append("Previous comparison window has too few usable clean laps; confidence is reduced.")
        if recent_median is None or previous_median is None:
            warnings.append("Lap trend requires both a recent and previous clean-lap window.")

        return FeatureMetricDriverScore(
            metric_id=self.definition.metric_id,
            metric_version=self.definition.version,
            analysis_scope=request.analysis_scope,
            comparison_scope=comparison_scope_for(request),
            entry=entry,
            value=normalized_score,
            rank=None,
            confidence=confidence_for_sample_count(confidence_window_count, config),
            sample_count=sample_count,
            window=build_window(recent_laps, request),
            components={
                "recent_median_lap_time_ms": round(recent_median, 3) if recent_median is not None else None,
                "previous_median_lap_time_ms": round(previous_median, 3) if previous_median is not None else None,
                "improvement_ms": round(improvement_ms, 3) if improvement_ms is not None else None,
                "previous_lap_numbers": [lap.lap_number for lap in previous_laps],
                "normalization": "field_relative_recent_vs_previous_window_improvement",
            },
            corrections=DEFAULT_CORRECTIONS.copy(),
            input_coverage=input_coverage,
            warnings=warnings,
        )
