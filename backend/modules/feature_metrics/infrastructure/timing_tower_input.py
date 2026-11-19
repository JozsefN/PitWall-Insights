"""Read a full-field timing timeline from the stored session in four bounded queries."""

from collections import defaultdict

from sqlalchemy import select

from modules.session_domain.domain.race_schedule import scheduled_race_laps
from modules.session_domain.infrastructure.db_models import (
    EntryLapRecord,
    EventSessionRecord,
    SessionEntryRecord,
    SessionRaceControlMessageRecord,
    SessionTrackStatusEventRecord,
    WeekendRecord,
)

from ..domain.review.timing_tower import (
    flag_series,
    gap_ms,
    lap_validity_reports,
    timed_lap,
    timing_series,
)


def load_timing_tower(db, session_id):
    session = db.execute(
        select(
            EventSessionRecord.session_name,
            EventSessionRecord.session_type,
            EventSessionRecord.session_time_origin_utc,
            EventSessionRecord.source_details["circuit_key"].label("circuit"),
            EventSessionRecord.source_details["race_positions"].label("race_positions"),
            EventSessionRecord.source_details["intervals"].label("intervals"),
            EventSessionRecord.source_details["classified_gaps"].label(
                "classified_gaps"
            ),
            WeekendRecord.season_year,
        )
        .join(WeekendRecord)
        .where(
            EventSessionRecord.id == session_id, EventSessionRecord.deleted_at.is_(None)
        )
    ).one_or_none()
    if session is None:
        return None

    name = session.session_name.strip().lower()
    sprint = name in {"sprint", "sprint race"}
    race = (
        name in {"race", "grand prix"} or (session.session_type or "").lower() == "race"
    )
    is_race = (race or sprint) and "qualifying" not in name and "shootout" not in name
    controls = (
        db.execute(
            select(
                SessionRaceControlMessageRecord.session_time_ms,
                SessionRaceControlMessageRecord.flag,
                SessionRaceControlMessageRecord.scope,
                SessionRaceControlMessageRecord.sector,
                SessionRaceControlMessageRecord.driver_number,
                SessionRaceControlMessageRecord.lap_number,
                SessionRaceControlMessageRecord.message,
            )
            .where(SessionRaceControlMessageRecord.session_id == session_id)
            .order_by(
                SessionRaceControlMessageRecord.session_time_ms,
                SessionRaceControlMessageRecord.id,
            )
        )
        .mappings()
        .all()
    )
    phases = (
        db.execute(
            select(
                SessionTrackStatusEventRecord.session_time_ms,
                SessionTrackStatusEventRecord.status,
            )
            .where(SessionTrackStatusEventRecord.session_id == session_id)
            .order_by(
                SessionTrackStatusEventRecord.session_time_ms,
                SessionTrackStatusEventRecord.id,
            )
        )
        .mappings()
        .all()
    )
    laps = db.execute(
        select(
            SessionEntryRecord.car_number,
            EntryLapRecord.lap_end_time_ms,
            EntryLapRecord.lap_number,
            EntryLapRecord.lap_position,
            EntryLapRecord.lap_time_ms,
            EntryLapRecord.pit_in_time_ms,
            EntryLapRecord.pit_out_time_ms,
            EntryLapRecord.is_deleted,
        )
        .select_from(SessionEntryRecord)
        .outerjoin(
            EntryLapRecord,
            (EntryLapRecord.session_entry_id == SessionEntryRecord.id)
            & (
                EntryLapRecord.lap_end_time_ms.is_not(None)
                & EntryLapRecord.is_generated.is_(False)
                & (EntryLapRecord.lap_number > 0)
            ),
        )
        .where(SessionEntryRecord.session_id == session_id)
        .order_by(EntryLapRecord.lap_end_time_ms, EntryLapRecord.lap_number)
    ).all()

    cars = {row.car_number for row in laps}
    ranks, gaps = (
        timing_series(session._mapping, session.session_time_origin_utc, cars)
        if is_race
        else ({}, {})
    )
    by_car = defaultdict(list)
    race_crossings = {}
    best = {}
    reports = lap_validity_reports(controls) if not is_race else {}
    for row in laps:
        if row.lap_end_time_ms is None:
            continue
        car = row.car_number
        if is_race:
            by_car[car].append([row.lap_end_time_ms, row.lap_number, row.lap_position])
            race_crossings.setdefault(row.lap_number, row.lap_end_time_ms)
        elif result := timed_lap(row, reports.get(car, ())):
            by_car[car].append(result)
            if not row.is_deleted:
                best[car] = min(best.get(car, row.lap_time_ms), row.lap_time_ms)

    leader_crossings = []
    for number, stamp in sorted(race_crossings.items(), key=lambda item: item[1]):
        if not leader_crossings or number > leader_crossings[-1][1]:
            leader_crossings.append([stamp, number])

    return {
        "kind": "race" if is_race else "timed",
        "scheduled_laps": (
            scheduled_race_laps(session.season_year, session.circuit)
            if is_race and not sprint
            else None
        ),
        "race_crossings": leader_crossings,
        "flags": flag_series(phases, controls),
        "ranks": ranks,
        "gaps": gaps,
        "race_laps": by_car if is_race else {},
        "timed_laps": {} if is_race else by_car,
        "best_laps": best,
        "classified_gaps": (
            {
                car: gap_ms(value)
                for car, value in (session.classified_gaps or {}).items()
                if car in cars
            }
            if is_race
            else {}
        ),
    }
