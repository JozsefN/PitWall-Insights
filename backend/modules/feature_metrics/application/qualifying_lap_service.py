"""Read field timing and bounded position samples for the qualifying lap map."""

from collections import defaultdict

from sqlalchemy import select

from modules.session_domain.infrastructure.models import EntryLapRecord, PositionSampleRecord

from ..domain.analysis.models import AnalysisLimitError
from ..domain.review.qualifying_lap import eligible_lap, qualifying_splits
from ..infrastructure.analysis_input import AnalysisInputProvider


MAX_POSITION_SAMPLES = 350_000


def qualifying_lap_map(db, session_id, entry_id, lap_number, minisectors):
    source = AnalysisInputProvider(db)
    session = source.session(session_id)
    name = session.session_name.lower()
    if "qualifying" not in name and "shootout" not in name:
        raise ValueError("Lap timing maps are available in qualifying lookback")
    entries = {entry.id for entry in source.entries(session_id)}
    laps = [lap for lap in source.rows(EntryLapRecord, EntryLapRecord.session_entry_id.in_(entries))
            if eligible_lap(lap)]
    laps.sort(key=lambda lap: (lap["lap_time_ms"], lap["lap_number"], lap["session_entry_id"]))
    result = {"laps": [{"entry_id": lap["session_entry_id"], "lap_number": lap["lap_number"],
                        "lap_time_ms": lap["lap_time_ms"]} for lap in laps],
              "field_driver_count": len(entries), "focus": None}
    if not laps:
        return result
    if entry_id is None and lap_number is None:
        focus = laps[0]
    else:
        focus = next((lap for lap in laps if lap["session_entry_id"] == entry_id and lap["lap_number"] == lap_number), None)
        if focus is None:
            raise ValueError("Choose a timed lap in this qualifying session")
    ids = [lap["id"] for lap in laps] if minisectors else [focus["id"], *(lap["id"] for lap in laps[:12])]
    positions = defaultdict(list)
    pos = PositionSampleRecord
    samples = db.execute(
        select(pos.lap_id, pos.session_time_ms, pos.x, pos.y)
        .where(pos.lap_id.in_(ids), pos.x.is_not(None), pos.y.is_not(None),
               (pos.x != 0) | (pos.y != 0))
        .order_by(pos.lap_id, pos.session_time_ms, pos.sample_seq)
        .limit(MAX_POSITION_SAMPLES + 1)
    ).mappings()
    for index, row in enumerate(samples):
        if index == MAX_POSITION_SAMPLES:
            raise AnalysisLimitError("Qualifying location data exceeds the sample limit")
        if not positions[row["lap_id"]] or positions[row["lap_id"]][-1]["session_time_ms"] != row["session_time_ms"]:
            positions[row["lap_id"]].append(row)
    return {
        **result,
        "focus": {"entry_id": focus["session_entry_id"], "lap_number": focus["lap_number"]},
        **qualifying_splits(laps, focus, positions, include_minisectors=minisectors),
    }
