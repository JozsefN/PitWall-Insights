"""Load bounded position windows for the session pit map."""

from collections import Counter, defaultdict
from datetime import datetime
from math import isfinite

from sqlalchemy import BigInteger, String, and_, column, exists, or_, values
from sqlalchemy.orm import Session

from modules.session_domain.domain.pit_map import (
    PIT_HINT_RADIUS_MS, PitFix, PitReport, PitTraceWindow, build_pit_map,
    pit_position_windows, reference_line,
)
from modules.session_domain.infrastructure.models import (
    EntryLapRecord, EventSessionRecord, PositionSampleRecord, SessionEntryRecord,
)


def load_pit_map(db: Session, session_id: str) -> dict | None:
    session = db.query(
        EventSessionRecord.source,
        EventSessionRecord.data_provider,
        EventSessionRecord.session_time_origin_utc,
        EventSessionRecord.source_details["pit_stops"],
        EventSessionRecord.source_details["pit_out_laps"],
    ).filter(
        EventSessionRecord.id == session_id,
        EventSessionRecord.deleted_at.is_(None),
        or_(EventSessionRecord.owner_user_id.is_(None), EventSessionRecord.owner_user_id == db.info.get("actor_user_id")),
    ).one_or_none()
    if session is None:
        return None
    source, provider, origin, rows, out_laps = session
    if (provider or source) != "openf1":
        return {**build_pit_map([], {}), "reported_visits": 0, "lane_source": None, "reference_entry_ids": []}

    entries = {str(row.car_number): (row.id, row.team_id) for row in db.query(
        SessionEntryRecord.car_number, SessionEntryRecord.id, SessionEntryRecord.team_id,
    ).filter(SessionEntryRecord.session_id == session_id)}
    reports = _pit_reports(rows if isinstance(rows, list) and origin else [], entries, origin)
    result = build_pit_map(reports, _position_fixes(db, pit_position_windows(reports)))
    lane_source = "pit_reports" if result["lane"] else None
    hints = []
    if not lane_source:
        hints = _trace_windows(db, session_id, out_laps)
        if hints:
            fixes = _position_fixes(db, pit_position_windows([], hints))
            racing_line = _racing_line(db, session_id, hints) if fixes and any(not hint.timed_crossings for hint in hints) else None
            result = build_pit_map([], fixes, hints=hints, racing_line=racing_line)
            lane_source = "position_traces" if result["lane"] else None
    counts = Counter(row.entry_id for row in [*reports, *hints])
    return {
        **result,
        "lane_source": lane_source,
        "reported_visits": len(reports),
        "reference_entry_ids": [] if lane_source else [entry for entry, _ in counts.most_common(2)],
    }


def _pit_reports(rows, entries, origin):
    reports = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get("driver_number")) not in entries:
            continue
        try:
            stamp = datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
            time_ms = round((stamp - origin).total_seconds() * 1000)
            lane = float(row.get("lane_duration") or row.get("pit_duration"))
            lap = int(row["lap_number"])
        except (KeyError, AttributeError, TypeError, ValueError, OverflowError):
            continue
        if not 5 <= lane <= 180 or lap < 1 or time_ms < 0:
            continue
        try:
            stationary = float(row.get("stop_duration"))
        except (TypeError, ValueError):
            stationary = None
        if stationary is not None and not 0 < stationary < lane:
            stationary = None
        entry_id, team_id = entries[str(row["driver_number"])]
        reports.append(PitReport(entry_id, team_id, lap, time_ms, round(lane * 1000), stationary))
    return reports


def _trace_windows(db, session_id, out_laps):
    out_lap_keys = {
        (str(item["driver_number"]), item["lap_number"])
        for item in (out_laps if isinstance(out_laps, list) else [])
        if isinstance(item, dict) and isinstance(item.get("lap_number"), int) and "driver_number" in item
    }
    lap = EntryLapRecord
    entry = SessionEntryRecord
    rows = db.query(entry.car_number, entry.team_id, lap).join(entry, lap.session_entry_id == entry.id).filter(
        entry.session_id == session_id,
        lap.is_generated.is_(False),
    ).order_by(entry.id, lap.lap_number).all()
    previous = {}
    pending_in = {}
    hints = []
    for number, team, current in rows:
        key = current.session_entry_id
        last = previous.get(key)
        previous[key] = current
        crossing_in = pending_in.get(key)
        paired = False
        # Compare in time order even when the normalized row contains both crossings.
        crossings = sorted((time, kind) for time, kind in (
            (current.pit_in_time_ms, "in"), (current.pit_out_time_ms, "out"),
        ) if time is not None)
        for time, kind in crossings:
            if kind == "in":
                crossing_in = time
            elif crossing_in is not None and time >= crossing_in:
                if 5_000 <= time - crossing_in <= 180_000:
                    hints.append(PitTraceWindow(key, team, current.lap_number, crossing_in, time, True))
                    paired = True
                crossing_in = None
        pending_in[key] = crossing_in
        changed_stint = (
            last is not None and last.lap_number + 1 == current.lap_number
            and last.stint_number is not None and current.stint_number is not None
            and last.stint_number != current.stint_number
        )
        start = current.lap_start_time_ms
        if not paired and start is not None and (changed_stint or (str(number), current.lap_number) in out_lap_keys):
            hints.append(PitTraceWindow(key, team, current.lap_number, max(0, start - PIT_HINT_RADIUS_MS), start + PIT_HINT_RADIUS_MS))
    return hints


def _racing_line(db, session_id, hints):
    lap = EntryLapRecord
    position = PositionSampleRecord
    hinted_laps = {(hint.entry_id, hint.lap_number) for hint in hints}
    candidates = db.query(
        lap.session_entry_id, lap.lap_number, lap.lap_start_time_ms, lap.lap_end_time_ms,
    ).join(SessionEntryRecord, lap.session_entry_id == SessionEntryRecord.id).filter(
        SessionEntryRecord.session_id == session_id,
        lap.lap_time_ms.between(20_000, 250_000),
        lap.lap_start_time_ms.is_not(None),
        lap.lap_end_time_ms.is_not(None),
        lap.pit_in_time_ms.is_(None), lap.pit_out_time_ms.is_(None),
        lap.is_generated.is_(False), lap.is_deleted.is_(False),
        exists().where(
            position.session_entry_id == lap.session_entry_id,
            position.session_time_ms.between(lap.lap_start_time_ms, lap.lap_end_time_ms),
        ),
    ).order_by(lap.is_accurate.desc(), lap.lap_time_ms, lap.id).limit(16)
    for entry_id, number, start, end in candidates:
        if (entry_id, number) in hinted_laps or (entry_id, number + 1) in hinted_laps:
            continue
        fixes = _position_fixes(db, [(entry_id, start, end)])
        if line := reference_line(fixes.get(entry_id, [])):
            return line
    return None


def _position_fixes(db, ranges):
    if not ranges:
        return {}

    position = PositionSampleRecord
    windows = values(
        column("entry_id", String), column("start_ms", BigInteger), column("end_ms", BigInteger),
        name="pit_windows",
    ).data(ranges)
    fixes = defaultdict(list)
    for entry_id, time_ms, x, y in db.query(
        position.session_entry_id, position.session_time_ms, position.x, position.y,
    ).select_from(windows).join(position, and_(
        position.session_entry_id == windows.c.entry_id,
        position.session_time_ms.between(windows.c.start_ms, windows.c.end_ms),
    )).filter(position.x.is_not(None), position.y.is_not(None)).order_by(
        position.session_entry_id, position.session_time_ms, position.sample_seq,
    ):
        if isfinite(x) and isfinite(y) and (x != 0 or y != 0):
            fixes[entry_id].append(PitFix(time_ms, (x, y)))
    return fixes
