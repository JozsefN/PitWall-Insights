from __future__ import annotations

from statistics import median

from modules.feature_metrics.domain.models import (
    AnalysisScope,
    FeatureMetricDataset,
    FeatureMetricDriverScore,
    FeatureMetricDriverScoreRequest,
    FeatureMetricInputCoverage,
    FeatureMetricLap,
    FeatureMetricWindow,
    FeatureMetricsConfig,
)

DEFAULT_CORRECTIONS = {
    "fuel": "not_applied",
    "traffic": "not_applied",
    "tire_age": "not_applied",
    "weather": "not_applied",
}


def select_clean_laps(
    laps: list[FeatureMetricLap],
    request: FeatureMetricDriverScoreRequest,
    config: FeatureMetricsConfig,
) -> list[FeatureMetricLap]:
    selected = [
        lap
        for lap in laps
        if _lap_is_usable(lap, config)
        and (request.lap_from is None or lap.lap_number >= request.lap_from)
        and (request.lap_to is None or lap.lap_number <= request.lap_to)
    ]
    selected.sort(key=lambda lap: lap.lap_number)
    return selected[-request.recent_laps :]


def select_previous_clean_laps(
    laps: list[FeatureMetricLap],
    recent_laps: list[FeatureMetricLap],
    request: FeatureMetricDriverScoreRequest,
    config: FeatureMetricsConfig,
) -> list[FeatureMetricLap]:
    if not recent_laps:
        return []

    first_recent_lap = recent_laps[0].lap_number
    selected = [
        lap
        for lap in laps
        if _lap_is_usable(lap, config)
        and lap.lap_number < first_recent_lap
        and (request.lap_from is None or lap.lap_number >= request.lap_from)
        and (request.lap_to is None or lap.lap_number <= request.lap_to)
    ]
    selected.sort(key=lambda lap: lap.lap_number)
    return selected[-request.recent_laps :]


def build_window(
    laps: list[FeatureMetricLap],
    request: FeatureMetricDriverScoreRequest,
) -> FeatureMetricWindow:
    return FeatureMetricWindow(
        lap_from=request.lap_from,
        lap_to=request.lap_to,
        recent_laps=request.recent_laps,
        lap_numbers=[lap.lap_number for lap in laps],
    )


def build_input_coverage(dataset: FeatureMetricDataset, entry_id: str | None = None) -> FeatureMetricInputCoverage:
    if entry_id is None:
        lap_count = sum(len(laps) for laps in dataset.laps_by_entry_id.values())
        entry_count = len(dataset.entries)
    else:
        lap_count = len(dataset.laps_by_entry_id.get(entry_id, []))
        entry_count = 1

    return FeatureMetricInputCoverage(
        loaded_inputs=dataset.loaded_inputs,
        missing_inputs=dataset.missing_inputs,
        entry_count=entry_count,
        lap_count=lap_count,
    )


def confidence_for_sample_count(sample_count: int, config: FeatureMetricsConfig) -> float:
    return round(min(1.0, sample_count / config.minimum_laps_for_score), 3)


def warnings_for_sample_count(sample_count: int, config: FeatureMetricsConfig) -> list[str]:
    if sample_count == 0:
        return ["No usable clean laps were available for this metric."]
    if sample_count < config.minimum_laps_for_score:
        return [
            f"Only {sample_count} usable clean lap(s) were available; confidence is reduced.",
        ]
    return []


def normalize_lower_is_better(raw_values: dict[str, float]) -> dict[str, float]:
    if not raw_values:
        return {}

    best = min(raw_values.values())
    worst = max(raw_values.values())
    if best == worst:
        return {entry_id: 100.0 for entry_id in raw_values}

    spread = worst - best
    return {
        entry_id: round(max(0.0, min(100.0, ((worst - value) / spread) * 100.0)), 2)
        for entry_id, value in raw_values.items()
    }


def normalize_higher_is_better(raw_values: dict[str, float]) -> dict[str, float]:
    if not raw_values:
        return {}

    best = max(raw_values.values())
    worst = min(raw_values.values())
    if best == worst:
        return {entry_id: 100.0 for entry_id in raw_values}

    spread = best - worst
    return {
        entry_id: round(max(0.0, min(100.0, ((value - worst) / spread) * 100.0)), 2)
        for entry_id, value in raw_values.items()
    }


def apply_ranks(scores: list[FeatureMetricDriverScore]) -> list[FeatureMetricDriverScore]:
    ranked_scores = sorted(
        [score for score in scores if score.value is not None],
        key=lambda score: (-float(score.value), score.entry.car_number),
    )

    previous_value: float | None = None
    previous_rank = 0
    for index, score in enumerate(ranked_scores, start=1):
        value = float(score.value)
        if previous_value is None or value != previous_value:
            previous_rank = index
            previous_value = value
        score.rank = previous_rank

    return scores


def median_lap_time_ms(laps: list[FeatureMetricLap]) -> float | None:
    times = [lap.lap_time_ms for lap in laps if lap.lap_time_ms is not None]
    return float(median(times)) if times else None


def median_absolute_deviation_ms(laps: list[FeatureMetricLap]) -> tuple[float | None, float | None]:
    median_ms = median_lap_time_ms(laps)
    if median_ms is None:
        return None, None

    deviations = [
        abs(float(lap.lap_time_ms) - median_ms)
        for lap in laps
        if lap.lap_time_ms is not None
    ]
    return float(median(deviations)) if deviations else None, median_ms


def comparison_scope_for(request: FeatureMetricDriverScoreRequest) -> AnalysisScope:
    return request.analysis_scope


def _lap_is_usable(lap: FeatureMetricLap, config: FeatureMetricsConfig) -> bool:
    if lap.lap_time_ms is None or lap.lap_time_ms <= 0:
        return False
    if config.exclude_deleted_laps and lap.is_deleted:
        return False
    if config.require_accurate_laps and not lap.is_accurate:
        return False
    if config.exclude_pit_laps and (lap.pit_in_time_ms is not None or lap.pit_out_time_ms is not None):
        return False
    return True
