"""Small indexed point-in-time reads; never return observations from the future."""

import math
import numpy as np
from sqlalchemy import select, true
from modules.session_domain.infrastructure.db_models import (
    SessionEntryRecord,
    CarTelemetrySampleRecord,
    PositionSampleRecord,
    EntryLapRecord,
    WeekendRecord,
)
from modules.feature_metrics.infrastructure.analysis_input import AnalysisInputProvider
from modules.feature_metrics.domain.analysis.common import json_safe


class SessionStateService:
    def __init__(self, db):
        self.db = db
        self.provider = AnalysisInputProvider(db)

    def get(self, session_id, at_ms, entry_ids=None):
        session = self.provider.session(session_id)
        records = self.provider.entries(session_id, entry_ids)
        ids = [row.id for row in records]
        modern = (
            session.source == "fastf1"
            and self.db.scalar(
                select(WeekendRecord.season_year).where(
                    WeekendRecord.id == session.weekend_id
                )
            )
            >= 2020
        )
        rows_by_kind = {}
        for name, model, limit in (
            ("car", CarTelemetrySampleRecord, 1),
            ("position", PositionSampleRecord, 2),
        ):
            source = select(model.__table__).where(
                model.session_entry_id == SessionEntryRecord.id,
                model.session_time_ms <= at_ms,
            )
            source = (
                source.order_by(model.session_time_ms.desc())
                .limit(limit)
                .correlate(SessionEntryRecord)
                .lateral()
            )
            rows_by_kind[name] = [
                dict(row)
                for row in self.db.execute(
                    select(source)
                    .select_from(SessionEntryRecord)
                    .join(source, true())
                    .where(SessionEntryRecord.id.in_(ids))
                ).mappings()
            ]
        laps = self.provider.rows(
            EntryLapRecord,
            EntryLapRecord.session_entry_id.in_(ids),
            EntryLapRecord.lap_start_time_ms <= at_ms,
            order=EntryLapRecord.lap_number,
        )
        reference = self.provider.reference(session_id, at_ms) if modern else None
        output = []
        for entry in records:
            car = next(
                (
                    row
                    for row in rows_by_kind["car"]
                    if row["session_entry_id"] == entry.id
                ),
                None,
            )
            positions = sorted(
                (
                    row
                    for row in rows_by_kind["position"]
                    if row["session_entry_id"] == entry.id
                ),
                key=lambda row: row["session_time_ms"],
                reverse=True,
            )
            position = positions[0] if positions else None
            age = at_ms - position["session_time_ms"] if position else None
            car_age = at_ms - car["session_time_ms"] if car else None
            point = None
            heading = None
            distance = None
            progress = None
            if (
                modern
                and position
                and all(
                    position.get(key) is not None and math.isfinite(position[key])
                    for key in ("x", "y")
                )
                and (position["x"] != 0 or position["y"] != 0)
            ):
                point = np.array([position["x"], position["y"]]) * 0.1
                if len(positions) > 1:
                    previous = positions[1]
                    elapsed = (
                        position["session_time_ms"] - previous["session_time_ms"]
                    ) / 1000
                    if 0 < elapsed <= 2 and all(
                        previous.get(key) is not None and math.isfinite(previous[key])
                        for key in ("x", "y")
                    ):
                        delta = point - np.array([previous["x"], previous["y"]]) * 0.1
                        speed = np.linalg.norm(delta) / elapsed * 3.6
                        if 0.1 < np.linalg.norm(delta) and speed <= 450:
                            heading = float(
                                np.rad2deg(np.arctan2(delta[1], delta[0])) % 360
                            )
                if reference is not None and age <= 2000:
                    distances, along = reference.project([point])
                    distance = float(distances[0])
                    progress = float(along[0])
            entry_laps = [lap for lap in laps if lap["session_entry_id"] == entry.id]
            completed = [
                lap
                for lap in entry_laps
                if lap.get("lap_end_time_ms") is not None
                and lap["lap_end_time_ms"] <= at_ms
                and (lap.get("lap_position") or 0) > 0
            ]
            current = next(
                (
                    lap
                    for lap in reversed(entry_laps)
                    if lap.get("lap_end_time_ms") is None
                    or at_ms < lap["lap_end_time_ms"]
                ),
                None,
            )
            pit_in = max(
                (
                    lap["pit_in_time_ms"]
                    for lap in entry_laps
                    if lap.get("pit_in_time_ms") is not None
                    and lap["pit_in_time_ms"] <= at_ms
                ),
                default=-1,
            )
            pit_out = max(
                (
                    lap["pit_out_time_ms"]
                    for lap in entry_laps
                    if lap.get("pit_out_time_ms") is not None
                    and lap["pit_out_time_ms"] <= at_ms
                ),
                default=-1,
            )
            output.append(
                dict(
                    entry_id=entry.id,
                    car_number=entry.car_number,
                    position_time_ms=position["session_time_ms"] if position else None,
                    position_age_ms=age,
                    position_is_stale=age is None or age > 2000 or point is None,
                    x_m=float(point[0]) if point is not None else None,
                    y_m=float(point[1]) if point is not None else None,
                    z_m=(
                        position["z"] * 0.1
                        if modern and position and position.get("z") is not None
                        else None
                    ),
                    heading_deg=heading,
                    reference_progress_pct=progress,
                    distance_from_reference_m=distance,
                    reported_position=(
                        completed[-1]["lap_position"] if completed else None
                    ),
                    reported_position_time_ms=(
                        completed[-1]["lap_end_time_ms"] if completed else None
                    ),
                    current_lap_number=current["lap_number"] if current else None,
                    in_known_pit_visit=pit_in > pit_out,
                    car_time_ms=car["session_time_ms"] if car else None,
                    car_age_ms=car_age,
                    car_is_stale=car_age is None or car_age > 2000,
                    speed_kph=car.get("speed_kph") if car else None,
                    gear=car.get("gear") if car else None,
                    throttle_pct=car.get("throttle_pct") if car else None,
                    brake_on=car.get("brake_on") if car else None,
                    source_position_status=(
                        position.get("track_status") if position else None
                    ),
                )
            )
        return json_safe(
            dict(
                session_id=session_id,
                at_time_ms=at_ms,
                entries=output,
                reference_lap_id=reference.lap_id if reference else None,
                warnings=[
                    "Coordinates are last-known observations, without extrapolation. Values older than 2000 ms are marked stale.",
                    "Reported position is the last completed-lap timing position, not a live race classification.",
                    "Reference progress is geometric and can be ambiguous on adjacent track sections; it is not an official timing measurement.",
                ],
            )
        )
