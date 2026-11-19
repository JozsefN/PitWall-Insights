"""Pack timing observations for local, seekable replay without telemetry requests."""

from collections import defaultdict
from math import isfinite
import re
from types import SimpleNamespace

from ..race_estimation.common import phase_at
from ..source_clock import timed_rows
from .circuit_flags import circuit_flags


def gap_ms(value):
    """Positive values are milliseconds, negative values encode laps down."""
    if isinstance(value, str):
        match = re.fullmatch(r"\+?(\d+)\s+LAPS?", value.strip(), re.IGNORECASE)
        if match:
            return -int(match[1]) or None
        try:
            value = float(value)
        except ValueError:
            return None
    if type(value) in (float, int) and 0 <= value < 100_000 and isfinite(value):
        return round(value * 1000)
    return None


def timing_series(details, origin, cars):
    ranks, gaps = defaultdict(list), defaultdict(list)
    for row in timed_rows(details.get("race_positions"), origin):
        car, rank, time = (
            row["driver_number"],
            row.get("position"),
            row["session_time_ms"],
        )
        if car in cars and type(rank) is int and rank > 0:
            previous = ranks[car][-1] if ranks[car] else None
            if previous is None or previous[1] != rank:
                ranks[car].append([time, rank])
    for row in timed_rows(details.get("intervals"), origin):
        car = row["driver_number"]
        if car in cars:
            gaps[car].append(
                [
                    row["session_time_ms"],
                    gap_ms(row.get("gap_to_leader")),
                    gap_ms(row.get("interval")),
                ]
            )
    return ranks, gaps


def flag_series(phases, controls):
    """Emit only status changes and keep marshal sectors independent of each other."""
    track_messages = {
        "CHEQUERED FLAG": "CHEQUERED",
        "TRACK CLEAR": "GREEN",
        "ALL CLEAR": "GREEN",
        "GREEN FLAG": "GREEN",
    }
    flag_rows = []
    for row in controls:
        if flag := track_messages.get(row["message"].strip().upper()):
            flag_rows.append({**row, "flag": flag, "scope": "Track"})
        elif row["flag"]:
            flag_rows.append(row)
    data = SimpleNamespace(track_status=phases, race_control=flag_rows)
    moments = sorted({row["session_time_ms"] for row in [*phases, *flag_rows]})
    frames = []
    for stamp in moments:
        state = circuit_flags(data, stamp)
        flag = state["track_flag"]
        if flag == "CLEAR" or (flag is None and phase_at(phases, stamp) == "1"):
            flag = "GREEN"
        if state["unlocated_caution"]:
            flag = "YELLOW"
        sectors = [item["number"] for item in state["sectors"]]
        if sectors and flag in (None, "GREEN"):
            local = {item["flag"] for item in state["sectors"]}
            flag = next(
                f"LOCAL {candidate}"
                for candidate in ("RED", "DOUBLE YELLOW", "YELLOW")
                if candidate in local
            )
        if flag or sectors or frames:
            row = [flag, sectors]
            if not frames or frames[-1][1:] != row:
                frames.append([stamp, *row])
    return frames


_LAP_DURATION = re.compile(r"\b(\d+):(\d{2})\.(\d{3})\b")
_CAR = re.compile(r"\bCAR\s+(\d+)\b")


def lap_validity_reports(controls):
    reports = defaultdict(list)
    for row in controls:
        message = row["message"].upper()
        if "LAP TIME" not in message or not (
            "DELETED" in message or "REINSTATED" in message
        ):
            continue
        car_match = _CAR.search(message)
        car = row["driver_number"] or (car_match[1] if car_match else None)
        if car is None:
            continue
        time_match = _LAP_DURATION.search(message)
        duration = (
            (int(time_match[1]) * 60 + int(time_match[2])) * 1000 + int(time_match[3])
            if time_match
            else None
        )
        reports[str(car)].append(
            (
                row["session_time_ms"],
                row["lap_number"],
                duration,
                "REINSTATED" in message,
            )
        )
    return reports


def timed_lap(row, reports):
    if (
        row.lap_time_ms is None
        or row.lap_time_ms < 10_000
        or row.pit_out_time_ms is not None
        or row.pit_in_time_ms is not None
    ):
        return None
    decisions = [
        [stamp, allowed]
        for stamp, lap, duration, allowed in reports
        if (
            abs(duration - row.lap_time_ms) <= 1
            if duration is not None
            else lap == row.lap_number
        )
        and stamp >= row.lap_end_time_ms - 1000
    ]
    # An archived exclusion with no recoverable report timestamp has no safe replay result.
    return (
        [row.lap_end_time_ms, row.lap_time_ms, decisions]
        if decisions or not row.is_deleted
        else None
    )
