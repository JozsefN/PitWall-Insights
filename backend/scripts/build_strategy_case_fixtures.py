"""Capture the minimal OpenF1 fields needed to replay published strategy cases."""

from argparse import ArgumentParser
from gzip import compress
import json
from pathlib import Path

from .build_intervention_archive import get

CASES = {2025: (9987, 10014, 10033), 2026: (11234,)}
FIELDS = {
    "laps": (
        "driver_number",
        "lap_number",
        "date_start",
        "is_pit_out_lap",
        "duration_sector_1",
        "duration_sector_2",
        "duration_sector_3",
    ),
    "pit": (
        "driver_number",
        "lap_number",
        "date",
        "lane_duration",
        "pit_duration",
        "stop_duration",
    ),
    "race_control": (
        "date",
        "category",
        "flag",
        "scope",
        "sector",
        "message",
        "driver_number",
    ),
}


if __name__ == "__main__":
    options = ArgumentParser(description=__doc__)
    options.add_argument("--cache-dir", type=Path, required=True)
    cache = options.parse_args().cache_dir
    cache.mkdir(parents=True, exist_ok=True)
    directory = Path(__file__).resolve().parents[1] / "tests/fixtures/strategy_cases"
    directory.mkdir(parents=True, exist_ok=True)
    for year, keys in CASES.items():
        sessions = {
            row["session_key"]: row
            for row in get("sessions", year=year, session_name="Race")
        }
        for key in keys:
            session = sessions[key]
            data = {
                name: session[name]
                for name in (
                    "session_key",
                    "date_start",
                    "circuit_key",
                    "circuit_short_name",
                )
            }
            for name, fields in FIELDS.items():
                data[name] = [
                    {k: row[k] for k in fields if k in row}
                    for row in get(name, cache, session_key=key)
                ]
            out = compress(
                json.dumps(data, separators=(",", ":")).encode("utf-8"), mtime=0
            )
            (directory / f"{key}.json.gz").write_bytes(out)
            print(key, len(out), flush=True)
