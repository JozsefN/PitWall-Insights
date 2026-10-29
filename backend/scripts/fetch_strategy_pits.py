"""Export source pit reports as a reviewable strategy context; no database mutation."""

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.ingestion.infrastructure.openf1_strategy_adapter import (
    OpenF1StrategyAdapter,
)
from modules.feature_metrics.domain.strategy.models import StrategyContext
from modules.feature_metrics.infrastructure.openf1_context import normalize_pit_reports
from modules.storage.infrastructure.db import SessionLocal
from modules.session_domain.infrastructure.db_models import (
    EventSessionRecord,
    WeekendRecord,
    SessionEntryRecord,
    CarTelemetrySampleRecord,
)

parser = argparse.ArgumentParser()
parser.add_argument("session_id")
parser.add_argument("--openf1-session-key", type=int, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
with SessionLocal() as db:
    session = db.get(EventSessionRecord, args.session_id)
    if not session or session.deleted_at:
        raise ValueError("Session not found")
    weekend = db.get(WeekendRecord, session.weekend_id)
    entries = {
        number: identity
        for number, identity in db.execute(
            select(SessionEntryRecord.car_number, SessionEntryRecord.id).where(
                SessionEntryRecord.session_id == session.id
            )
        )
    }
    first = db.execute(
        select(
            CarTelemetrySampleRecord.source_time_utc,
            CarTelemetrySampleRecord.session_time_ms,
        )
        .where(
            CarTelemetrySampleRecord.session_entry_id.in_(list(entries.values())),
            CarTelemetrySampleRecord.source_time_utc.is_not(None),
        )
        .order_by(
            CarTelemetrySampleRecord.session_entry_id,
            CarTelemetrySampleRecord.session_time_ms,
        )
        .limit(1)
    ).first()
    if first is None:
        raise ValueError(
            "Materialized dated car observations are needed to identify the feed-clock origin"
        )
    origin = first[0] - timedelta(milliseconds=first[1])
    expected_year = weekend.season_year
    expected_name = session.session_name
    expected_start = session.scheduled_start_utc
adapter = OpenF1StrategyAdapter()
metadata = adapter.get("sessions", session_key=args.openf1_session_key)
if len(metadata) != 1:
    raise ValueError("OpenF1 session key must identify exactly one session")
record = metadata[0]
start = datetime.fromisoformat(record["date_start"].replace("Z", "+00:00"))
if (
    record["year"] != expected_year
    or record["session_name"].lower() != expected_name.lower()
    or expected_start is None
    or abs((start - expected_start).total_seconds()) > 10800
):
    raise ValueError(
        "OpenF1 session metadata does not match the selected PitWall session"
    )
rows = adapter.get("pit", session_key=args.openf1_session_key)
reports = normalize_pit_reports(
    rows,
    entries_by_car=entries,
    clock_origin=origin,
    session_key=args.openf1_session_key,
)
context = StrategyContext(
    known_at_ms=0,
    source_note="Retrospective OpenF1 pit enrichment. Report known_at uses source event plus visit duration plus 15 seconds, not measured original publication time.",
    pit_observations=reports,
)
args.output.write_text(context.model_dump_json(indent=2) + "\n", encoding="utf-8")
print(
    json.dumps(
        {
            "reports": len(reports),
            "stationary_reports": sum(
                row.stationary_duration_s is not None for row in reports
            ),
            "output": str(args.output),
            "database_modified": False,
        }
    )
)
