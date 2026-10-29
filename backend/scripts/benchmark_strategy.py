"""Measure authenticated strategy inputs, private context, scenario search and cache on a real race."""

import argparse
import json
from pathlib import Path
import secrets
import sys
from time import monotonic
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.feature_metrics.infrastructure.db_models import (
    StrategyContextRecord,
    SessionAnalysisCacheRecord,
)
from sqlalchemy import select, func

parser = argparse.ArgumentParser()
parser.add_argument("session_id")
parser.add_argument("--context-file", type=Path)
parser.add_argument("--exercise-scenario", action="store_true")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
token = None
user_id = None


def api(method, path, data=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(
        "http://127.0.0.1:8000" + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
        method=method,
    )
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read())


try:
    auth = api(
        "POST",
        "/api/auth/signup",
        dict(
            email=f"strategy-benchmark-{secrets.token_hex(8)}@example.com",
            password=secrets.token_urlsafe(24),
        ),
    )
    token = auth["access_token"]
    user_id = api("GET", "/api/auth/session")["user_id"]
    catalog = api("GET", "/api/strategy/catalog")
    entries = api("GET", f"/api/sessions/{args.session_id}/entries")
    focus = next(
        (entry for entry in entries if entry["car_number"] == "1"), entries[0]
    )["id"]
    timeline = api("GET", f"/api/sessions/{args.session_id}/replay-timeline")
    cutoff = (timeline["start_time_ms"] + timeline["end_time_ms"]) // 2
    base = f"/api/strategy/sessions/{args.session_id}"
    context = (
        json.loads(args.context_file.read_text(encoding="utf-8"))
        if args.context_file
        else dict(
            known_at_ms=0,
            source_note="Benchmark with no unobserved strategy assumptions",
        )
    )
    if args.exercise_scenario:
        context.update(
            tyre_curves=[
                dict(
                    compound=name,
                    base_delta_s=offset,
                    degradation_s_per_lap=slope,
                    max_valid_age_laps=80,
                    uncertainty_s_per_lap=0.4,
                    provenance="user_scenario",
                    source_uri="test:benchmark_assumption_not_fitted",
                )
                for name, offset, slope in (
                    ("SOFT", -0.5, 0.14),
                    ("MEDIUM", 0, 0.10),
                    ("HARD", 0.3, 0.08),
                )
            ],
            tyre_inventory={
                focus: [
                    dict(set_id="test-medium-one", compound="MEDIUM"),
                    dict(set_id="test-hard-one", compound="HARD"),
                ]
            },
            pit_loss=dict(
                green_s=20,
                vsc_s=12,
                sc_s=10,
                uncertainty_s=2,
                provenance="user_scenario",
                source_uri="test:net_pit_assumption_not_lane_duration",
            ),
            rules=dict(
                profile_id="test-scenario-only",
                season_year=2025,
                minimum_distinct_compounds=2,
                source_uri="test:scenario_rule_not_certified_fia",
            ),
        )
        context[
            "source_note"
        ] += " Numerical workflow validation only: tyre curves, inventory and pit loss are intentionally synthetic scenario assumptions."
    saved = api("POST", base + "/contexts", context)
    payload = dict(
        as_of_ms=cutoff,
        focus_entry_id=focus,
        context_id=saved["context_id"],
        remaining_laps=20 if args.exercise_scenario else None,
    )
    started = monotonic()
    first = api("POST", base + "/evaluate", payload)
    first_seconds = monotonic() - started
    started = monotonic()
    cached = api("POST", base + "/evaluate", payload)
    cached_seconds = monotonic() - started
    assert cached["cache_hit"]
    assert all(value["as_of_ms"] == cutoff for value in first["values"])
    selected = [
        value
        for value in first["values"]
        if value["metric_id"]
        in (
            "strategy_recent_pace_s",
            "pit_latest_lane_duration_s",
            "pit_latest_stationary_duration_s",
            "pit_latest_lane_excess_s",
            "strategy_best_gain_vs_stay_out_s",
        )
    ]
    summary = dict(
        session_id=args.session_id,
        as_of_ms=cutoff,
        definitions=len(catalog["metrics"]),
        results=len(first["values"]),
        first_request_seconds=round(first_seconds, 3),
        cached_request_seconds=round(cached_seconds, 3),
        cache_hit_on_repeat=cached["cache_hit"],
        recommendation_status=first["recommendation_status"],
        plans_returned=len(first["plans"]),
        planning=first["models"]["planning"],
        pace_model_status=first["models"]["pace"]["status"],
        coverage=first["readiness"]["coverage"],
        sample_values=selected,
        scenario_coefficients_are_synthetic=args.exercise_scenario,
        warnings=[
            "Real telemetry/context route validation does not validate the synthetic scenario as an optimal race strategy."
        ],
    )
    args.output.write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
finally:
    if user_id:
        with SessionLocal() as db:
            db.query(UserRecord).filter(UserRecord.id == user_id).delete()
            db.commit()
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(StrategyContextRecord)
                    .where(StrategyContextRecord.owner_user_id == user_id)
                )
                == 0
            )
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(SessionAnalysisCacheRecord)
                    .where(SessionAnalysisCacheRecord.owner_user_id == user_id)
                )
                == 0
            )
