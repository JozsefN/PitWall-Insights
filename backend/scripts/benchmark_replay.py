"""Measure real replay startup without deleting source data or using existing credentials.

Run from backend: .venv/Scripts/python.exe scripts/benchmark_replay.py SESSION_ID --drivers 2
API and worker must be running. Missing telemetry is cached for normal reuse.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import secrets
import sys
from uuid import uuid4
from time import monotonic, sleep
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.session_domain.infrastructure.models import EventSessionRecord, SessionEntryRecord, EntryLapRecord, EntryStintRecord, CarTelemetrySampleRecord, PositionSampleRecord

parser = argparse.ArgumentParser()
parser.add_argument("session_id")
parser.add_argument("--drivers", type=int, default=2)
parser.add_argument("--timeout", type=int, default=180)
parser.add_argument("--isolated", action="store_true", help="Clone core metadata into a temporary session to measure fresh database materialization. Provider disk cache is retained.")
args = parser.parse_args()
token = None
user_id = None
isolated_id = None

def clone_row(record, **updates):
    values = {column.name: getattr(record, column.name) for column in record.__table__.columns}
    values.update(updates)
    return type(record)(**values)

def cleanup_fixture(session_id):
    with SessionLocal() as db:
        fixture = db.get(EventSessionRecord, session_id)
        if fixture is None:
            return
        if fixture.source_session_key != f"benchmark:{session_id}":
            raise ValueError("Refusing to clean a session that is not this benchmark's fixture")
        entry_ids = [row[0] for row in db.query(SessionEntryRecord.id).filter(SessionEntryRecord.session_id == session_id)]
        # Remove leaf samples first, avoiding expensive per-lap SET NULL cascades.
        for model in (CarTelemetrySampleRecord, PositionSampleRecord):
            db.query(model).filter(model.session_entry_id.in_(entry_ids)).delete(synchronize_session=False)
        db.query(EventSessionRecord).filter(EventSessionRecord.id == session_id).delete()
        db.commit()

def api(method, path, data=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request("http://127.0.0.1:8000" + path,
                  data=json.dumps(data).encode() if data is not None else None,
                  headers=headers, method=method)
    with urlopen(req, timeout=60) as response:
        raw = response.read()
        return json.loads(raw) if raw else None

try:
    if args.isolated:
        with SessionLocal() as db:
            original = db.get(EventSessionRecord, args.session_id)
            if original is None:
                raise ValueError("Session not found")
            isolated_id = str(uuid4())
            db.add(clone_row(original, id=isolated_id, source_session_key=f"benchmark:{isolated_id}",
                             import_profile="core", telemetry_status="not_loaded"))
            db.flush()
            entries = db.query(SessionEntryRecord).filter(SessionEntryRecord.session_id == args.session_id).order_by(SessionEntryRecord.car_number).limit(args.drivers).all()
            for entry in entries:
                entry_id = str(uuid4())
                db.add(clone_row(entry, id=entry_id, session_id=isolated_id))
                db.flush()
                for model in (EntryLapRecord, EntryStintRecord):
                    for row in db.query(model).filter(model.session_entry_id == entry.id).all():
                        db.add(clone_row(row, id=str(uuid4()), session_entry_id=entry_id))
            db.commit()
        args.session_id = isolated_id
    auth = api("POST", "/api/auth/signup", {"email": f"replay-benchmark-{secrets.token_hex(8)}@example.com",
                                            "password": secrets.token_urlsafe(24)})
    token = auth["access_token"]
    user_id = api("GET", "/api/auth/session")["user_id"]
    entries = api("GET", f"/api/sessions/{args.session_id}/entries")[:args.drivers]
    started = monotonic()
    timeline = api("GET", f"/api/sessions/{args.session_id}/replay-timeline")
    prepared = api("POST", "/api/telemetry/materialization/ensure", {
        "session_id": args.session_id, "entry_ids": [e["id"] for e in entries],
        "kinds": ["car", "position"], "scope": "session",
    })
    cache_hit = prepared["ready"]
    job = None
    last_stage = None
    while not prepared["ready"]:
        job = api("GET", f'/api/telemetry/materialization/jobs/{prepared["job_id"]}')
        if last_stage != job["progress_stage"]:
            print(f'{monotonic()-started:.2f}s: {job["progress_stage"]}', file=sys.stderr, flush=True)
            last_stage = job["progress_stage"]
        if job["status"] == "completed":
            break
        if job["status"] in {"failed", "cancelled"}:
            raise RuntimeError(job["error_message"])
        if monotonic() - started > args.timeout:
            raise TimeoutError(f'Replay exceeded {args.timeout}s; stage={job["progress_stage"]}')
        sleep(1)
    ready_seconds = monotonic() - started
    interval = max(500, ((timeline["end_time_ms"] - timeline["start_time_ms"] + 1799999) // 1800000) * 100)
    def read_samples(task):
        entry, kind = task
        path = f'/api/sessions/{args.session_id}/entries/{entry["id"]}/telemetry/{kind}'
        samples = api("GET", path + f'?limit=20000&sample_interval_ms={interval}&session_time_from_ms={timeline["start_time_ms"]}&session_time_to_ms={timeline["end_time_ms"]}')
        return {"car_number": entry["car_number"], "kind": kind, "samples": len(samples),
                "first_ms": samples[0]["session_time_ms"] if samples else None,
                "last_ms": samples[-1]["session_time_ms"] if samples else None}
    with ThreadPoolExecutor(max_workers=4) as pool:
        samples = list(pool.map(read_samples, [(entry, kind) for entry in entries for kind in ["car", "position"]]))
    result = {"session_id": args.session_id, "drivers": len(entries), "cache_hit": cache_hit,
              "isolated_database_materialization": args.isolated,
              "preparation_seconds": round(ready_seconds, 3), "startup_seconds": round(monotonic()-started, 3),
              "target_seconds": args.timeout, "timeline": timeline, "sample_interval_ms": interval,
              "rows_written": job["rows_written"] if job else None, "samples": samples}
    if any(not item["samples"] for item in samples):
        raise RuntimeError("Replay response has missing driver telemetry: " + json.dumps(result))
    print(json.dumps(result, indent=2), flush=True)
finally:
    try:
        if isolated_id:
            cleanup_fixture(isolated_id)
    finally:
        if user_id:
            with SessionLocal() as db:
                db.query(UserRecord).filter(UserRecord.id == user_id).delete()
                db.commit()
