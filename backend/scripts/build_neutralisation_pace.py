"""Archive dimensionless same-driver SC/VSC lap ratios from completed OpenF1 races."""

from argparse import ArgumentParser
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
from statistics import median
from time import sleep

from modules.feature_metrics.domain.review.intervention import (
    intervention,
    is_race_green,
    warning_kind,
)

from .build_intervention_archive import get


def neutralisation_ratios(controls, laps, start, finish):
    clock, yellows = [(start, "green")], []
    for row in sorted(controls, key=lambda row: row["date"]):
        stamp = datetime.fromisoformat(row["date"]).timestamp()
        if not start <= stamp < finish:
            continue
        text = str(row.get("message") or "").upper()
        if any(mark in text for mark in ("TRACK DECLARED WET", "WET TRACK", "RAIN IN")):
            return {}
        phase = intervention(row) or ("green" if is_race_green(row) else None)
        if phase and phase != clock[-1][1]:
            clock.append((stamp, phase))
        if warning_kind(row) in ("yellow", "double_yellow"):
            yellows.append(stamp)
    if not any(phase in ("sc", "vsc") for _, phase in clock):
        return {}
    stamps = [stamp for stamp, _ in clock]
    by_driver = defaultdict(dict)
    for row in laps:
        if row.get("driver_number") is not None and row.get("lap_number") is not None:
            by_driver[row["driver_number"]][row["lap_number"]] = row
    by_phase = defaultdict(list)
    for history in by_driver.values():
        observed = {}
        for lap, row in history.items():
            duration, date = row.get("lap_duration"), row.get("date_start")
            if (
                lap < 3
                or not date
                or not isinstance(duration, (int, float))
                or not 35 <= duration <= 330
                or row.get("is_pit_out_lap")
                or history.get(lap + 1, {}).get("is_pit_out_lap")
            ):
                continue
            begin = datetime.fromisoformat(date).timestamp()
            end = begin + duration
            if not start <= begin < end <= finish:
                continue
            left, right = bisect_right(stamps, begin) - 1, bisect_right(stamps, end) - 1
            if left != right:
                continue
            phase = clock[left][1]
            if phase == "green" and any(
                begin - 30 <= caution <= end for caution in yellows
            ):
                continue
            observed[lap] = phase, duration
        driver = defaultdict(list)
        for lap, (phase, duration) in observed.items():
            if phase not in ("sc", "vsc"):
                continue
            clean = [
                time
                for other, (state, time) in observed.items()
                if state == "green" and abs(lap - other) <= 7
            ]
            if len(clean) >= 2:
                ratio = duration / median(clean)
                if 1.03 <= ratio <= 2.8:
                    driver[phase].append(ratio)
        for phase, ratios in driver.items():
            by_phase[phase].append(median(ratios))
    return {
        phase: {"ratio": round(median(ratios), 4), "drivers": len(ratios)}
        for phase, ratios in by_phase.items()
        if len(ratios) >= 3
    }


def archive(cache, history):
    output, skipped = [], []
    covered = set(history["session_keys"])
    for year in history["seasons"]:
        for race in get("sessions", year=year, session_name="Race"):
            key = race["session_key"]
            if key not in covered:
                continue
            try:
                controls = get("race_control", cache, session_key=key)
                if not any(intervention(row) in ("sc", "vsc") for row in controls):
                    continue
                if any(
                    "TRACK DECLARED WET" in str(row.get("message") or "").upper()
                    for row in controls
                ):
                    continue
                start = datetime.fromisoformat(race["date_start"]).timestamp()
                finish = min(
                    datetime.fromisoformat(row["date"]).timestamp()
                    for row in controls
                    if row.get("flag") == "CHEQUERED"
                    and datetime.fromisoformat(row["date"]).timestamp() > start
                )
                laps = get("laps", cache, session_key=key)
                ratios = neutralisation_ratios(controls, laps, start, finish)
                if ratios:
                    output.append(
                        {
                            "race": key,
                            "circuit": race["circuit_key"],
                            "available_after": max(
                                finish,
                                datetime.fromisoformat(race["date_end"]).timestamp(),
                            ),
                            "phases": ratios,
                        }
                    )
                print(year, key, ratios, flush=True)
                sleep(0.8)
            except (OSError, KeyError, TypeError, ValueError) as error:
                skipped.append(key)
                print(year, key, str(error), flush=True)
    return {
        "source": "https://openf1.org/docs/#laps",
        "races": output,
        "unavailable_races": skipped,
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    options = parser.parse_args()
    options.cache_dir.mkdir(parents=True, exist_ok=True)
    shared = Path(__file__).resolve().parents[2] / "shared"
    history = json.loads(
        (shared / "intervention-history.json").read_text(encoding="utf-8")
    )
    output = archive(options.cache_dir, history)
    if len(output["races"]) < 5:
        raise SystemExit(
            "Insufficient prior race pace data. Existing archive preserved."
        )
    (shared / "neutralisation-pace.json").write_text(
        json.dumps(output, separators=(",", ":")) + "\n", encoding="utf-8"
    )
