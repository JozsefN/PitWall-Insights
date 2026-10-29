"""Walk forward one matched lap at a time; score forecasts only after their targets occur."""

import argparse
import json
from pathlib import Path
import sys
from time import monotonic
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.storage.infrastructure.db import SessionLocal
from modules.feature_metrics.infrastructure.analysis_input import AnalysisInputProvider
from modules.feature_metrics.domain.analysis.models import AnalysisRequest
from modules.feature_metrics.domain.strategy.models import StrategyRequest
from modules.decision_engine.application.strategy_service import evaluate_strategy

parser = argparse.ArgumentParser()
parser.add_argument("session_id")
parser.add_argument("--focus-car", default="1")
parser.add_argument("--rival-car", default="4")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
started = monotonic()
with SessionLocal() as db:
    provider = AnalysisInputProvider(db)
    entries = provider.entries(args.session_id)
    by_car = {entry.car_number: entry.id for entry in entries}
    focus = by_car[args.focus_car]
    rival = by_car[args.rival_car]
    data = provider.load(
        args.session_id,
        AnalysisRequest(entry_ids=[focus, rival], sample_interval_ms=1000),
        required_inputs={
            "car",
            "position",
            "laps",
            "track_status",
            "weather",
            "race_control",
            "reference_line",
        },
    )
    fingerprint = provider.fingerprint(args.session_id)
a = next(entry for entry in data.entries if entry.id == focus)
b = next(entry for entry in data.entries if entry.id == rival)
own = {
    row["lap_number"]: row
    for row in a.laps
    if row.get("lap_end_time_ms") is not None and not row.get("is_generated")
}
other = {
    row["lap_number"]: row
    for row in b.laps
    if row.get("lap_end_time_ms") is not None and not row.get("is_generated")
}
rows = []
for number in sorted(own.keys() & other.keys()):
    if number < 5 or number + 1 not in own or number + 1 not in other:
        continue
    cutoff = max(own[number]["lap_end_time_ms"], other[number]["lap_end_time_ms"])
    result = evaluate_strategy(
        data,
        StrategyRequest(
            as_of_ms=cutoff,
            focus_entry_id=focus,
            rival_entry_ids=[rival],
            sample_interval_ms=1000,
        ),
    )
    metrics = {
        value.metric_id: value.value
        for value in result.values
        if value.entry_id == focus and value.rival_entry_id == rival
    }
    gap = (own[number]["lap_end_time_ms"] - other[number]["lap_end_time_ms"]) / 1000
    advantage = metrics.get("rival_pace_advantage_s_per_lap")
    if advantage is None:
        continue
    predicted = gap - advantage
    # These target values are read exclusively for scoring after forecasting the prefix.
    actual = (
        own[number + 1]["lap_end_time_ms"] - other[number + 1]["lap_end_time_ms"]
    ) / 1000
    future_clear = all(
        row.get("track_status") == "1"
        and row.get("pit_in_time_ms") is None
        and row.get("pit_out_time_ms") is None
        for row in (own[number + 1], other[number + 1])
    )
    rows.append(
        dict(
            decision_lap=number,
            as_of_ms=cutoff,
            target_lap=number + 1,
            predicted_gap_s=predicted,
            actual_gap_s=actual,
            error_s=predicted - actual,
            unchanged_gap_error_s=gap - actual,
            target_green_nonpit=future_clear,
        )
    )


def scores(selected):
    if not selected:
        return None
    errors = np.array([row["error_s"] for row in selected])
    baseline = np.array([row["unchanged_gap_error_s"] for row in selected])
    return dict(
        samples=len(selected),
        mae_s=float(np.mean(abs(errors))),
        rmse_s=float(np.sqrt(np.mean(errors**2))),
        bias_s=float(np.mean(errors)),
        p90_abs_error_s=float(np.percentile(abs(errors), 90)),
        unchanged_gap_mae_s=float(np.mean(abs(baseline))),
    )


output = dict(
    session_id=args.session_id,
    focus_car=args.focus_car,
    rival_car=args.rival_car,
    data_fingerprint=fingerprint,
    seconds=round(monotonic() - started, 3),
    all_targets=scores(rows),
    green_nonpit_targets=scores([row for row in rows if row["target_green_nonpit"]]),
    forecasts=rows,
    limitations=[
        "One-step observational forecast; not a counterfactual pit-strategy backtest.",
        "Future status is used only to stratify evaluation, never to build the forecast.",
        "Historical lap flags/deletion metadata may be revised; this is event-time rather than original-arrival-time replay.",
        "No claim that the pace forecast beats the unchanged-gap baseline on every race.",
    ],
)
args.output.write_text(
    json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8"
)
print(
    json.dumps(
        {key: value for key, value in output.items() if key != "forecasts"}, indent=2
    )
)
