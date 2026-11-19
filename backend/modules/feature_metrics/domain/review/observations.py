"""Source observations for the review API, with bounded media links."""

import re
from collections import Counter
from statistics import median
from modules.session_domain.domain.source_media import driver_headshot, media_url

from ..source_clock import timed_rows
from ..race_estimation.common import number, at
from ..strategy.common import clean_laps


COLOURS = {2048: "yellow", 2049: "green", 2051: "purple", 2064: "pitlane"}


def driver_cards(data, details, entries, cutoff, qualifying, final_results_visible):
    annotations = {
        (str(row.get("driver_number")), row.get("lap_number")): row.get("sectors")
        for row in details.get("qualifying_segments", [])
    }
    cards = []
    for entry in data.entries:
        identity = entries[entry.id]
        clean = clean_laps(entry, cutoff)
        best = min(clean, key=lambda lap: lap["lap_time_ms"], default=None)
        phases = []
        reported = details.get("qualifying_times", {}).get(entry.car_number, [])
        if qualifying and final_results_visible:
            for phase in range(3):
                time_s = number(reported[phase]) if phase < len(reported) else None
                if time_s is None or time_s <= 0:
                    continue
                matching = [
                    row
                    for row in entry.laps
                    if not row.get("is_deleted")
                    and row.get("lap_end_time_ms") is not None
                    and row["lap_end_time_ms"] <= cutoff
                    and row.get("lap_time_ms") == round(time_s * 1000)
                ]
                lap = matching[0] if len(matching) == 1 else None
                raw = (
                    annotations.get((entry.car_number, lap["lap_number"]))
                    if lap
                    else None
                )
                phases.append(
                    {
                        "phase": phase + 1,
                        "lap_time_s": time_s,
                        "lap_number": lap["lap_number"] if lap else None,
                        "lap_match": "unique_duration" if lap else "unresolved",
                        "provider_colours": (
                            [
                                (
                                    [
                                        COLOURS.get(code, "unknown")
                                        for code in sector[:100]
                                        if isinstance(code, int)
                                    ]
                                    if isinstance(sector, list)
                                    else []
                                )
                                for sector in raw[:3]
                            ]
                            if isinstance(raw, list)
                            else []
                        ),
                    }
                )
        headshot = driver_headshot(details.get("driver_headshots"), entry.car_number)
        cards.append(
            {
                "entry_id": entry.id,
                "car_number": entry.car_number,
                **identity,
                "headshot_url": headshot,
                "best_clean_lap_s": best["lap_time_ms"] / 1000 if best else None,
                "best_clean_lap_number": best["lap_number"] if best else None,
                "recent_clean_lap_numbers": [lap["lap_number"] for lap in clean[-6:]],
                "qualifying": phases,
            }
        )
    for phase in range(1, 4):
        values = sorted(
            (
                phase_row
                for card in cards
                for phase_row in card["qualifying"]
                if phase_row["phase"] == phase
            ),
            key=lambda row: row["lap_time_s"],
        )
        for row in values:
            row["gap_to_phase_best_s"] = round(
                row["lap_time_s"] - values[0]["lap_time_s"], 3
            )
    return cards


def radio_messages(details, origin, driver_ids, cutoff):
    output = []
    seen = set()
    for row in reversed(timed_rows(details.get("team_radio"), origin)):
        entry = driver_ids.get(row["driver_number"])
        url = media_url(row.get("recording_url"), {"livetiming.formula1.com"})
        stamp = row["session_time_ms"]
        if entry and url and stamp + 1000 <= cutoff and (entry, url) not in seen:
            output.append(
                {
                    "entry_id": entry,
                    "time_ms": stamp,
                    "known_at_ms": stamp + 1000,
                    "recording_url": url,
                }
            )
            seen.add((entry, url))
    return output


def race_control_incidents(data, driver_ids, cutoff):
    reports = []
    for row in data.race_control:
        if row["session_time_ms"] + 1000 > cutoff:
            continue
        message = str(row.get("message") or "")
        text = message.upper()
        ids = {
            driver_ids[car]
            for car in re.findall(r"\bCAR\s+(\d+)\b", text)
            if car in driver_ids
        }
        if row.get("session_entry_id"):
            ids.add(row["session_entry_id"])
        if not ids:
            continue
        if any(
            term in text
            for term in ("TRACK LIMIT", "LEFT THE TRACK", "LAP TIME DELETED")
        ):
            kind = (
                "track_limits"
                if "TRACK LIMIT" in text or "LEFT THE TRACK" in text
                else "lap_deletion"
            )
        elif (
            any(
                term in text for term in ("COLLISION", "CONTACT", "CAUSING A COLLISION")
            )
            and "NO CONTACT" not in text
        ):
            kind = "contact_report"
        elif "DAMAGE" in text or "FRONT WING" in text:
            kind = "damage_report"
        else:
            continue
        reports.append(
            {
                "kind": kind,
                "entry_ids": sorted(ids),
                "time_ms": row["session_time_ms"],
                "message": message,
                "lap_number": row.get("lap_number"),
                "source": "race_control",
            }
        )
    return reports[-200:]


def incident_summary(data, reports, cutoff):
    by_entry = {entry.id: entry for entry in data.entries}
    counts = Counter(
        (entry, report["kind"]) for report in reports for entry in report["entry_ids"]
    )
    recent = {}
    for report in reports:
        if report["kind"] in ("damage_report", "contact_report"):
            for entry in report["entry_ids"]:
                recent[entry] = report
    changes = []
    for entry_id, report in recent.items():
        if entry_id not in by_entry:
            continue
        stamp = report["time_ms"]
        laps = clean_laps(by_entry[entry_id], cutoff)
        before = [row for row in laps if row["lap_end_time_ms"] <= stamp][-4:]
        after = [row for row in laps if (row.get("lap_start_time_ms") or 0) >= stamp][
            :4
        ]
        if len(before) < 3 or len(after) < 3:
            continue
        signatures = {
            (row.get("compound"), row.get("stint_number")) for row in [*before, *after]
        }
        if len(signatures) != 1 or any(None in signature for signature in signatures):
            continue
        previous = median(row["lap_time_ms"] for row in before) / 1000
        following = median(row["lap_time_ms"] for row in after) / 1000
        changes.append(
            {
                "entry_id": entry_id,
                "report_time_ms": stamp,
                "before_s": previous,
                "after_s": following,
                "pace_change_s": following - previous,
                "samples_before": len(before),
                "samples_after": len(after),
                "method": "Observed same-stint pace change around a race-control report. Traffic, tyres, weather and effort can contribute.",
            }
        )
    return {
        "report_counts": [
            {"entry_id": entry, "report_kind": kind, "count": count}
            for (entry, kind), count in sorted(counts.items())
        ],
        "post_report_pace": changes,
    }


def weather_timeline(data, cutoff):
    rows = [
        row
        for row in data.weather
        if cutoff - 1800000 <= row["session_time_ms"] <= cutoff
    ]
    latest = at(rows, cutoff, 120000)

    def entry(row):
        speed = number(row.get("wind_speed_kph"))
        return {
            "time_ms": row["session_time_ms"],
            "wind_speed_ms": speed / 3.6 if speed is not None else None,
            "wind_direction_deg": row.get("wind_direction_deg"),
            "rain_reported": row.get("rainfall"),
            "track_temperature_c": row.get("track_temp_c"),
            "air_temperature_c": row.get("air_temp_c"),
        }

    return {
        "current": entry(latest) if latest else None,
        "timeline": [entry(row) for row in rows[-60:]],
        "rainfall_mm": None,
        "segment_rainfall_mm": None,
        "surface_wetness": None,
        "reason": "The circuit weather feed supplies a rain flag and one regional observation at a time.",
    }
