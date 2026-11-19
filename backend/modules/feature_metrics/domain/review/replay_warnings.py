"""Build the strategy incident feed from visible timing reports and speed samples."""

import re

from ..race_estimation.common import phase_at
from ..strategy.pits import latest_pit_transitions
from .intervention import (
    LABELS,
    HORIZON_S,
    age_matched_cohort,
    current_race_control,
    incident_cohort,
    probability_forecast,
    race_episodes,
    signal_class,
    warning_kind,
)
from .observations import race_control_incidents


def replay_warnings(data, cutoff, start_ms, before_epoch, circuit, archive, telemetry):
    visible = [
        row for row in data.race_control if row["session_time_ms"] + 1000 <= cutoff
    ]
    ids = {entry.car_number: entry.id for entry in data.entries}
    phase = phase_at(data.track_status, cutoff)
    reported, pit_entry_closed = current_race_control(visible)
    if reported is not None and (reported != "1" or phase in ("4", "5", "6", "7")):
        phase = reported
    episodes = race_episodes(visible, start_ms)
    active = episodes[-1] if episodes else None
    forecast, cohort, age_s = None, [], 0
    active_ms = None
    finished = any(str(row.get("flag") or "").upper() == "CHEQUERED" for row in visible)
    if (
        not finished
        and active
        and active.response_ms is None
        and active.clear_ms is None
        and phase in ("1", "2")
    ):
        age_s = (cutoff - active.start_ms) / 1000
        if age_s <= HORIZON_S:
            active_ms = active.start_ms
            reference = age_matched_cohort(archive, age_s, before_epoch)
            cohort, scope = incident_cohort(
                reference, signal_class(active.signals), age_s, circuit
            )
            forecast = probability_forecast(cohort, age_s, scope, reference)

    warnings = []
    retired = set()
    for row in visible:
        stamp = row["session_time_ms"]
        if stamp < start_ms:
            continue
        if str(row.get("flag") or "").upper() == "CHEQUERED":
            break
        message = str(row.get("message") or "")
        kind = warning_kind(row)
        cars = re.findall(
            r"(?<=\bCAR )\d+|(?<=\bCARS )\d+|(?<= AND )\d+(?=\s*\()", message.upper()
        )
        entries = {ids[car] for car in cars if car in ids}
        if row.get("session_entry_id"):
            entries.add(row["session_entry_id"])
        if kind == "retired":
            retired.update(entries)
        if kind and cutoff - stamp <= 180000:
            warnings.append(
                {
                    "time_ms": stamp,
                    "kind": kind,
                    "title": LABELS[kind],
                    "entry_ids": sorted(entries),
                    "detail": message,
                    "source": "race_control",
                    "forecast": (
                        forecast
                        if active_ms is not None and stamp >= active_ms
                        else None
                    ),
                }
            )

    confirmed_stamps = {row["time_ms"] for row in warnings if row["kind"] == "contact"}
    if not finished:
        for report in race_control_incidents(data, ids, cutoff):
            stamp = report["time_ms"]
            text = report["message"].upper()
            if (
                report["kind"] != "contact_report"
                or stamp in confirmed_stamps
                or not max(start_ms, cutoff - 180000) <= stamp
                or "NOTED" not in text
                or "PENALTY" in text
            ):
                continue
            warnings.append(
                {
                    "time_ms": stamp,
                    "kind": "contact_mentioned",
                    "title": "Contact mentioned by race control",
                    "entry_ids": report["entry_ids"],
                    "detail": report["message"],
                    "source": "race_control",
                    "forecast": None,
                }
            )

    if (
        not finished
        and phase in ("1", "2")
        and any(
            lap.get("lap_end_time_ms") is not None
            for entry in data.entries
            for lap in entry.laps
        )
    ):
        for entry in data.entries:
            candidate = _vehicle_warning(entry, telemetry.get(entry.id, []), cutoff)
            if candidate:
                warnings.append(candidate)
    warnings.sort(key=lambda row: row["time_ms"], reverse=True)
    return (
        warnings[:12],
        retired,
        {
            "forecast": forecast,
            "episode_start_ms": active_ms,
            "phase": phase,
            "pit_entry_closed": pit_entry_closed,
        },
        cohort,
        age_s,
    )


def _vehicle_warning(entry, samples, cutoff):
    if not samples or cutoff - samples[-1]["session_time_ms"] > 2000:
        return None
    last = samples[-1]
    entered, exited = latest_pit_transitions(entry, cutoff)
    last_pit = max(entered, exited)
    if entered > exited or (last_pit >= 0 and 0 <= cutoff - last_pit <= 15000):
        return None
    if last["speed_kph"] > 25:
        return None
    start = last["session_time_ms"]
    for row in reversed(samples[:-1]):
        if (
            row["speed_kph"] > 5
            or last["speed_kph"] > 5
            or start - row["session_time_ms"] > 1500
        ):
            break
        start = row["session_time_ms"]
    if last["session_time_ms"] - start >= 4000:
        title = "Car appears stopped"
        kind = "telemetry_stop"
        detail = f"At or below 5 km/h for {(last['session_time_ms'] - start) / 1000:.0f} s. Check race control for confirmation."
    else:
        spike = max(
            (
                row["speed_kph"]
                for row in samples
                if 0 < last["session_time_ms"] - row["session_time_ms"] <= 2200
            ),
            default=0,
        )
        if spike - last["speed_kph"] < 100:
            return None
        title = "Abrupt slowdown"
        kind = "telemetry_slowdown"
        detail = f"Speed dropped from {spike:.0f} to {last['speed_kph']:.0f} km/h within 2.2 s."
    return {
        "time_ms": start,
        "kind": kind,
        "title": title,
        "entry_ids": [entry.id],
        "detail": detail,
        "source": "telemetry_candidate",
        "forecast": None,
    }
