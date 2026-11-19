"""Chronological neutralisation pit-cost backtest against the green-cost baseline."""

import json
from pathlib import Path
from statistics import mean

from modules.feature_metrics.domain.review.replay_pit import archive_stop_ratio


def evaluate(races, phase):
    results = []
    for race in races:
        phases = race["phases"]
        if not {"green", phase} <= phases.keys():
            continue
        prior = [
            row for row in races if row["available_after"] < race["available_after"]
        ]
        ratio = archive_stop_ratio(prior, race["circuit"], phase)
        broad = archive_stop_ratio(prior, None, phase)
        if ratio is None or broad is None:
            continue
        green, observed = phases["green"]["median_s"], phases[phase]["median_s"]
        predicted = green * min(1, ratio[0])
        results.append(
            {
                "race": race["race"],
                "observed_s": observed,
                "green_s": green,
                "predicted_s": round(predicted, 3),
                "error_s": abs(predicted - observed),
                "green_error_s": abs(green - observed),
                "pooled_error_s": abs(green * min(1, broad[0]) - observed),
            }
        )
    return {
        "scored_races": len(results),
        "model_mae_s": round(mean(row["error_s"] for row in results), 3),
        "green_baseline_mae_s": round(mean(row["green_error_s"] for row in results), 3),
        "pooled_baseline_mae_s": round(
            mean(row["pooled_error_s"] for row in results), 3
        ),
        "featured_races": [
            {key: row[key] for key in ("race", "observed_s", "green_s", "predicted_s")}
            for row in results
            if row["race"] in (10014, 10033, 9987, 11234)
        ],
    }


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[2] / "shared/pit-sector-loss.json"
    archive = json.loads(path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "archive_races": len(archive["races"]),
                "comparison": "Observed target-race green cost anchors both predictions. Only earlier races set the neutralisation adjustment.",
                **{phase: evaluate(archive["races"], phase) for phase in ("sc", "vsc")},
            },
            indent=2,
        )
    )
