"""Refresh messages once their UTC timestamps can be aligned to the feed clock."""

from datetime import datetime, timezone
from sqlalchemy import select, delete, insert, update, text
from modules.session_domain.infrastructure.models import (
    SessionEntryRecord,
    SessionRaceControlMessageRecord,
    EventSessionRecord,
)
from modules.session_domain.infrastructure.models.common import generate_uuid


def refresh_race_control(db, session_id, payloads):
    if not payloads:
        return 0  # Missing source data must not erase existing context.
    # Same lock as telemetry persistence; replacing this small context is atomic.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
        {"key": f"telemetry:persist:{session_id}"},
    )
    entries = {
        source_key: entry_id
        for source_key, entry_id in db.execute(
            select(SessionEntryRecord.source_entry_key, SessionEntryRecord.id).where(
                SessionEntryRecord.session_id == session_id
            )
        )
    }
    rows = []
    seen = set()
    for payload in payloads:
        key = (
            payload.session_time_ms,
            payload.message,
            payload.driver_number,
            payload.category,
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            dict(
                id=generate_uuid(),
                session_id=session_id,
                session_entry_id=entries.get(payload.source_entry_key),
                session_time_ms=payload.session_time_ms,
                source_time_utc=payload.source_time_utc,
                category=payload.category,
                message=payload.message,
                flag=payload.flag,
                scope=payload.scope,
                sector=payload.sector,
                lap_number=payload.lap_number,
                driver_number=payload.driver_number,
            )
        )
    db.execute(
        delete(SessionRaceControlMessageRecord).where(
            SessionRaceControlMessageRecord.session_id == session_id
        )
    )
    db.execute(insert(SessionRaceControlMessageRecord), rows)
    db.execute(
        update(EventSessionRecord)
        .where(EventSessionRecord.id == session_id)
        .values(imported_at=datetime.now(timezone.utc))
    )
    return len(rows)
