"""Build phase-specific stop-loss benchmarks from OpenF1 timing sectors."""

from argparse import ArgumentParser
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
from statistics import median
from time import sleep

from modules.feature_metrics.domain.review.pit_sector_loss import (
    pit_sector_losses,
    sector_windows,
)
from modules.feature_metrics.domain.source_clock import timed_rows
from modules.feature_metrics.domain.strategy.common import mad
from .build_intervention_archive import get


def sector_observations(laps, pits, controls, origin, finish_ms):
    def offset(date):
        return round((datetime.fromisoformat(date) - origin).total_seconds() * 1000)

    by_driver, out_laps = defaultdict(list), defaultdict(set)
    for row in laps:
        if row.get("date_start") is None or row.get("lap_number") is None:
            continue
        driver = str(row["driver_number"])
        lap = row["lap_number"]
        by_driver[driver].append(
            {
                "lap_number": lap,
                "lap_start_time_ms": offset(row["date_start"]),
                **{
                    f"sector_{n}_time_ms": round(value * 1000)
                    for n in (1, 2, 3)
                    if (value := row.get(f"duration_sector_{n}"))
                },
            }
        )
        if row.get("is_pit_out_lap"):
            out_laps[driver].add(lap)
    reports = []
    for report in pits:
        if report.get("date") is None or report.get("lap_number") is None:
            continue
        stamp = offset(report["date"])
        lane = report.get("lane_duration", report.get("pit_duration"))
        if lane is None or lane <= 0:
            continue
        reports.append(
            {
                "entry_id": str(report["driver_number"]),
                "lap_number": report["lap_number"],
                "event_time_ms": stamp,
                "known_at_ms": stamp + round(lane * 1000) + 15000,
                "lane_duration_s": lane,
                "stationary_duration_s": report.get("stop_duration"),
            }
        )
    windows = (
        window
        for driver, rows in by_driver.items()
        for window in sector_windows(driver, rows, out_laps[driver])
    )
    return pit_sector_losses(windows, reports, timed_rows(controls, origin), finish_ms)


def archive(cache, history, selected):
    rows, skipped = [], []
    calibrated = {row["race"] for row in history["episodes"]}
    for year in history["seasons"]:
        for race in get("sessions", year=year, session_name="Race"):
            key = race["session_key"]
            if key not in history["session_keys"] or (selected and key not in selected):
                continue
            try:
                controls = get("race_control", cache, session_key=key)
                if any(
                    any(
                        term in str(row.get("message") or "").upper()
                        for term in ("TRACK DECLARED WET", "WET TRACK", "RAIN IN")
                    )
                    for row in controls
                ):
                    continue
                origin = datetime.fromisoformat(race["date_start"])
                finish = min(
                    datetime.fromisoformat(row["date"])
                    for row in controls
                    if row.get("flag") == "CHEQUERED"
                    and datetime.fromisoformat(row["date"]) > origin
                )
                race_laps = get("laps", cache, session_key=key)
                stops = get("pit", cache, session_key=key)
                values = sector_observations(
                    race_laps,
                    stops,
                    controls,
                    origin,
                    round((finish - origin).total_seconds() * 1000),
                )
                summary = {}
                for phase in ("green", "sc", "vsc"):
                    samples = [
                        row["net_loss_s"] for row in values if row["phase"] == phase
                    ]
                    if len(samples) >= (3 if phase == "green" else 2):
                        summary[phase] = {
                            "median_s": round(median(samples), 3),
                            "samples": len(samples),
                            "scatter_s": round(mad(samples), 3),
                        }
                if summary:
                    rows.append(
                        {
                            "race": key,
                            "circuit": race["circuit_key"],
                            "available_after": max(
                                finish.timestamp(),
                                datetime.fromisoformat(race["date_end"]).timestamp(),
                            ),
                            "phases": summary,
                        }
                    )
                print(year, key, summary, flush=True)
            except (OSError, KeyError, ValueError) as error:
                skipped.append(key)
                print(year, key, str(error), flush=True)
            if key not in calibrated:
                sleep(0.8)
    return {
        "source": "https://openf1.org/docs/#laps",
        "races": rows,
        "unavailable_races": skipped,
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--session-keys", type=int, nargs="+")
    options = parser.parse_args()
    options.cache_dir.mkdir(parents=True, exist_ok=True)
    shared = Path(__file__).resolve().parents[2] / "shared"
    history = json.loads(
        (shared / "intervention-history.json").read_text(encoding="utf-8")
    )
    result = archive(options.cache_dir, history, set(options.session_keys or []))
    if len(result["races"]) < 3:
        raise SystemExit("The archive needs at least three measured races")
    (shared / "pit-sector-loss.json").write_text(
        json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8"
    )
