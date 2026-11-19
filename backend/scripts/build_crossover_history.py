"""Capture reproducible OpenF1 crossover races and derive past sector pace priors."""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
import gzip
import json
from pathlib import Path
from statistics import median

from modules.decision_engine.domain.weather_crossover import field_comparison
from modules.feature_metrics.domain.analysis.models import AnalysisData, EntryData
from modules.feature_metrics.domain.review.pace import rain_state
from modules.feature_metrics.domain.review.replay_sectors import SectorTiming, family
from modules.feature_metrics.domain.snapshot import causal_snapshot
from modules.feature_metrics.infrastructure.openf1_context import normalize_pit_reports
from modules.normalization.domain.openf1_quality import derive_track_status
from .build_intervention_archive import get

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend/tests/fixtures/strategy_crossover"
CASES = {2023: (9141, 9149), 2024: (9531, 9558, 9636), 2025: (9693, 9947, 10014)}
FIELDS = {
    "laps": (
        "driver_number",
        "lap_number",
        "date_start",
        "lap_duration",
        "duration_sector_1",
        "duration_sector_2",
        "duration_sector_3",
        "is_pit_out_lap",
    ),
    "stints": (
        "driver_number",
        "lap_start",
        "lap_end",
        "compound",
        "stint_number",
        "tyre_age_at_start",
    ),
    "pit": (
        "session_key",
        "driver_number",
        "date",
        "lap_number",
        "lane_duration",
        "stop_duration",
        "pit_duration",
    ),
    "weather": ("date", "rainfall"),
    "race_control": ("date", "message", "flag", "scope", "sector"),
}


def collect(cache):
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for year, keys in CASES.items():
        sessions = {
            row["session_key"]: row
            for row in get("sessions", year=year, session_name="Race")
        }
        for key in keys:
            race = sessions[key]
            data = {
                name: race[name] for name in ("session_key", "date_start", "date_end")
            }
            for endpoint, fields in FIELDS.items():
                rows = get(endpoint, cache, session_key=key)
                data[endpoint] = [
                    {name: row[name] for name in fields if name in row} for row in rows
                ]
            (FIXTURES / f"{key}.json.gz").write_bytes(
                gzip.compress(json.dumps(data, separators=(",", ":")).encode(), mtime=0)
            )
            print(key, "fixture ready", flush=True)


def read_fixture(key):
    with gzip.open(FIXTURES / f"{key}.json.gz", "rt", encoding="utf-8") as stream:
        return json.load(stream)


def normalize(raw):
    origin = datetime.fromisoformat(raw["date_start"]) - timedelta(hours=2)

    def stamp(date):
        return round((datetime.fromisoformat(date) - origin).total_seconds() * 1000)

    drivers = defaultdict(list)
    stints = defaultdict(list)
    out_laps = defaultdict(set)
    for item in raw["stints"]:
        stints[str(item["driver_number"])].append(item)
    for lap in raw["laps"]:
        if not lap.get("date_start"):
            continue
        start, num, car = (
            stamp(lap["date_start"]),
            lap["lap_number"],
            str(lap["driver_number"]),
        )
        stint = next(
            (
                item
                for item in stints[car]
                if item["lap_start"] <= num <= (item["lap_end"] or 1000)
            ),
            {},
        )
        total = lap.get("lap_duration")
        row = {
            "lap_number": num,
            "lap_start_time_ms": start,
            "lap_end_time_ms": start + round(total * 1000) if total else None,
            "lap_time_ms": round(total * 1000) if total else None,
            "compound": stint.get("compound"),
        }
        if stint.get("tyre_age_at_start") is not None:
            row["tyre_life"] = num - stint["lap_start"] + stint["tyre_age_at_start"] + 1
        cumulative = start
        for sector in (1, 2, 3):
            duration = lap.get(f"duration_sector_{sector}")
            if duration is None:
                break
            value = round(duration * 1000)
            cumulative += value
            row[f"sector_{sector}_time_ms"] = value
            row[f"sector_{sector}_session_time_ms"] = cumulative
        drivers[car].append(row)
        if lap.get("is_pit_out_lap"):
            out_laps[car].add(num)
    events = derive_track_status(
        [
            {
                "SessionTime": stamp(item["date"]),
                "Scope": item.get("scope"),
                "Flag": item.get("flag"),
                "Message": item.get("message"),
                "Sector": item.get("sector"),
            }
            for item in raw["race_control"]
        ]
    )
    controls = [
        {"session_time_ms": stamp(item["date"]), **item} for item in raw["race_control"]
    ]
    weather = [
        {"session_time_ms": stamp(item["date"]), **item} for item in raw["weather"]
    ]
    end = stamp(raw["date_end"])
    data = AnalysisData(
        str(raw["session_key"]),
        0,
        end,
        entries=[
            EntryData(car, car, laps=sorted(laps, key=lambda row: row["lap_number"]))
            for car, laps in drivers.items()
        ],
        weather=weather,
        race_control=controls,
        track_status=[
            {"session_time_ms": event["SessionTime"], "status": event["Status"]}
            for event in events
        ],
    )
    pits = []
    for row in raw["pit"]:
        try:
            pits.extend(
                normalize_pit_reports(
                    [row],
                    entries_by_car={car: car for car in drivers},
                    clock_origin=origin,
                    session_key=raw["session_key"],
                )
            )
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    reports = [
        {
            **pit.model_dump(),
            "out_lap_reported": pit.lap_number + 1 in out_laps[pit.entry_id],
        }
        for pit in pits
    ]
    return data, reports, out_laps, stamp


def prior_for(raw):
    data, reports, out_laps, _ = normalize(raw)
    changes = defaultdict(lambda: defaultdict(list))
    # Sample around split-verified changes and during mixed opening phases.
    stamps = {
        int(i["known_at_ms"] + delay)
        for i in reports
        for delay in (30_000, 65_000, 105_000)
    }
    stamps.update(range(7_300_000, min(data.end_ms, 8_000_000), 30_000))
    for at in sorted(
        {
            _stamp // 15_000 * 15_000
            for _stamp in stamps
            if 7_200_000 <= _stamp < data.end_ms
        }
    ):
        timing = SectorTiming(data, causal_snapshot(data, at), reports, out_laps)
        current = {family(compound) for compound in timing.current.values()}
        if len(current) < 2:
            continue
        rain = rain_state(data, at)
        if rain is None:
            continue
        condition = "heavy" if rain and "WET" in current else "rain" if rain else "dry"
        for (first, second), (values, references, scouts) in field_comparison(
            timing
        ).items():
            if len(values) >= 2 and references >= 2 and scouts >= 2:
                changes[condition][f"{first}:{second}"].append(
                    sum(row["gain_s"] for row in values)
                )
    full = SectorTiming(data, causal_snapshot(data, data.end_ms), reports, out_laps)
    warmup = {
        f"{tyre}:{side}": round(max(0.0, median(losses)), 3)
        for (tyre, side), losses in full.warmup_samples().items()
        if len(losses) >= 2
    }
    return {
        "race": raw["session_key"],
        "warmup": warmup,
        "available_after": datetime.fromisoformat(raw["date_end"]).timestamp(),
        "conditions": {
            condition: {pair: round(median(values), 3) for pair, values in rows.items()}
            for condition, rows in changes.items()
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--cached-fixtures", action="store_true")
    args = parser.parse_args()
    if not args.cached_fixtures:
        args.cache_dir.mkdir(parents=True, exist_ok=True)
        collect(args.cache_dir)
    prior = []
    for keys in CASES.values():
        for key in keys:
            row = prior_for(read_fixture(key))
            if row["conditions"] or row["warmup"]:
                prior.append(row)
            print(key, row["conditions"], flush=True)
    (ROOT / "shared/crossover-history.json").write_text(
        json.dumps({"races": prior}, indent=2) + "\n", encoding="utf-8"
    )
