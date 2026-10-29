"""Repair message alignment for an existing session without replacing its telemetry.

This resolves the provider's true telemetry clock origin. It preserves source caches
and writes only race-control context. Run for sessions with available provider data.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from modules.ingestion.infrastructure.fastf1_adapter import FastF1Adapter
from modules.ingestion.domain.models import TelemetrySelection
from modules.normalization.application.service import NormalizationService
from modules.session_domain.domain.models import SessionImportRequest
from modules.session_domain.infrastructure.db_models import (
    EventSessionRecord,
    WeekendRecord,
)
from modules.session_domain.infrastructure.race_control import refresh_race_control
from modules.storage.infrastructure.db import SessionLocal

parser = argparse.ArgumentParser()
parser.add_argument("session_id")
args = parser.parse_args()
with SessionLocal() as db:
    session = db.get(EventSessionRecord, args.session_id)
    if session is None or session.deleted_at is not None:
        raise ValueError("Session not found")
    weekend = db.get(WeekendRecord, session.weekend_id)
    if session.source != "fastf1":
        raise ValueError("Backfill currently supports FastF1 only")
    request = SessionImportRequest(
        season_year=weekend.season_year,
        round_number=weekend.round_number,
        session_name=session.session_name,
        source_session_key=session.source_session_key,
        import_profile="full",
    )
bundle = FastF1Adapter().load_session(
    request, telemetry_selection=TelemetrySelection(frozenset(), frozenset())
)
snapshot = NormalizationService().build_snapshot(bundle, ttl_hours=1)
with SessionLocal() as db:
    count = refresh_race_control(db, args.session_id, snapshot.race_control_messages)
    db.commit()
print(
    json.dumps(
        {
            "session_id": args.session_id,
            "source_messages": len(bundle.race_control_messages),
            "persisted_messages": count,
            "clock_origin_utc": str(bundle.metadata.session_time_origin_utc),
        }
    )
)
