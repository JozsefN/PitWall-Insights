"""Real authenticated analytics, cache and point-in-time routes; no provider calls."""

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

parser = argparse.ArgumentParser()
parser.add_argument("session_id")
parser.add_argument("--interval", type=int, default=500)
parser.add_argument("--output", type=Path)
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
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read())


try:
    auth = api(
        "POST",
        "/api/auth/signup",
        {
            "email": f"analysis-benchmark-{secrets.token_hex(8)}@example.com",
            "password": secrets.token_urlsafe(24),
        },
    )
    token = auth["access_token"]
    user_id = api("GET", "/api/auth/session")["user_id"]
    catalog = api("GET", "/api/feature-metrics/analytics/catalog")
    path = f"/api/feature-metrics/sessions/{args.session_id}"
    start = monotonic()
    response = api("POST", path + "/analytics", {"sample_interval_ms": args.interval})
    elapsed = monotonic() - start
    print(
        f"First analysis: {elapsed:.3f}s, {len(response['metrics'])} results",
        file=sys.stderr,
        flush=True,
    )
    start = monotonic()
    cached = api("POST", path + "/analytics", {"sample_interval_ms": args.interval})
    cached_elapsed = monotonic() - start
    at_ms = (response["start_time_ms"] + response["end_time_ms"]) // 2
    start = monotonic()
    state = api("GET", path + f"/state?at_ms={at_ms}")
    state_elapsed = monotonic() - start
    assert cached["cache_hit"], "Second request should reuse persisted analysis"
    assert all(
        row["position_time_ms"] is None or row["position_time_ms"] <= at_ms
        for row in state["entries"]
    )
    summary = {
        "session_id": args.session_id,
        "definitions": catalog["metric_count"],
        "metric_results": len(response["metrics"]),
        "first_request_seconds": round(elapsed, 3),
        "first_request_cache_hit": response["cache_hit"],
        "cached_request_seconds": round(cached_elapsed, 3),
        "state_request_seconds": round(state_elapsed, 3),
        "coverage": response["coverage"],
        "event_count": response["total_event_count"],
        "events_returned": len(response["events"]),
        "unavailable_metric_results": sum(
            row["status"] != "ok" for row in response["metrics"]
        ),
        "state_entries": len(state["entries"]),
        "fresh_positions": sum(
            not row["position_is_stale"] for row in state["entries"]
        ),
        "reference_lap_id": state["reference_lap_id"],
        "sample_metrics": [
            row
            for row in response["metrics"]
            if (
                row["entry_id"] == state["entries"][0]["entry_id"]
                and row["metric_id"]
                in [
                    "max_speed_kph",
                    "best_lap_ms",
                    "reference_lap_length_m",
                    "possible_incident_count",
                ]
            )
            or row["metric_id"] in ["mean_wind_speed_kph", "race_control_message_count"]
        ],
    }
    payload = json.dumps(summary, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
finally:
    if user_id:
        with SessionLocal() as db:
            db.query(UserRecord).filter(UserRecord.id == user_id).delete()
            db.commit()
