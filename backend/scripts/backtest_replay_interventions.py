"""Chronological Safety Car probability check against an age-matched pooled baseline."""

import json
from pathlib import Path
from statistics import mean

from modules.feature_metrics.domain.review.intervention import (
    HORIZON_S,
    age_matched_cohort,
    first_outcome,
    incident_cohort,
    phase_at_pit,
    probability_forecast,
    signal_class,
)


def score(episodes, age, delay=None):
    results = []
    for row in episodes:
        response, clear = row["response_s"], row["clear_s"]
        if (response is not None and response <= age) or (
            clear is not None and clear <= age
        ):
            continue
        if row["coverage_s"] < age + HORIZON_S and response is None:
            continue
        incident = signal_class(
            [signal for signal in row["signals"] if signal[0] <= age]
        )
        earlier = age_matched_cohort(episodes, age, row["available_after"])
        cohort, scope = incident_cohort(earlier, incident, age, row["circuit"])
        forecast = probability_forecast(cohort, age, scope, earlier)
        if forecast is None:
            continue
        narrow = probability_forecast(cohort, age, scope)

        if delay is not None:
            target = age + delay
            if row["coverage_s"] < target:
                continue
            actual = next(
                (
                    phase
                    for phase, start, end in row["phases"]
                    if phase in ("sc", "vsc") and start <= target < end
                ),
                "other",
            )
            predictions = {
                "model_error": phase_at_pit(cohort, age, delay, forecast),
                "narrow_error": phase_at_pit(cohort, age, delay),
                "baseline_error": phase_at_pit(earlier, age, delay),
            }
            if any(not value for value in predictions.values()):
                continue
            errors = {
                name: sum(
                    (value[phase] - (actual == phase)) ** 2 for phase in ("sc", "vsc")
                )
                + (1 - sum(value.values()) - (actual == "other")) ** 2
                for name, value in predictions.items()
            }
            results.append(
                {"race": row["race"], "actual": int(actual == "sc"), **errors}
            )
            continue

        def observed(item):
            return int(first_outcome(item, age) == "sc")

        actual = observed(row)
        pooled = (sum(observed(item) for item in earlier) + 0.5) / (len(earlier) + 2)
        results.append(
            {
                "race": row["race"],
                "actual": actual,
                "model_error": (forecast["outcomes_pct"]["sc"] / 100 - actual) ** 2,
                "narrow_error": (narrow["outcomes_pct"]["sc"] / 100 - actual) ** 2,
                "baseline_error": (pooled - actual) ** 2,
            }
        )
    return {
        "episode_age_seconds": age,
        **({"pit_delay_seconds": delay} if delay is not None else {}),
        "scored_episodes": len(results),
        "races": len({row["race"] for row in results}),
        ("safety_car_first" if delay is None else "safety_car_at_projected_pit"): sum(
            row["actual"] for row in results
        ),
        "regularized_brier": (
            round(mean(row["model_error"] for row in results), 5) if results else None
        ),
        "incident_cohort_only_brier": (
            round(mean(row["narrow_error"] for row in results), 5) if results else None
        ),
        "pooled_brier": (
            round(mean(row["baseline_error"] for row in results), 5)
            if results
            else None
        ),
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    archive = json.loads(
        (root / "shared/intervention-history.json").read_text(encoding="utf-8")
    )
    print(
        json.dumps(
            {
                "source_races": len(archive["session_keys"]),
                "source_episodes": len(archive["episodes"]),
                "horizon_seconds": HORIZON_S,
                "chronological_scores": [
                    score(archive["episodes"], age) for age in (0, 15, 30)
                ],
                "pit_phase_occupancy_scores": [
                    score(archive["episodes"], 0, delay) for delay in (30, 60, 90)
                ],
            },
            indent=2,
        )
    )
