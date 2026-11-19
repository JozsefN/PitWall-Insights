"""Read the shared race distances and race-specific sporting rules."""

from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _read_schedule(revision):
    return json.loads(_SCHEDULE.read_text(encoding="utf-8"))


_SCHEDULE = Path(__file__).resolve().parents[4] / "shared" / "race-distances.json"


def race_schedule():
    try:
        return _read_schedule(_SCHEDULE.stat().st_mtime_ns)
    except FileNotFoundError:
        return {}


def scheduled_race_laps(season, circuit):
    schedule = race_schedule()
    if season in schedule.get("verifiedSeasons", []):
        return schedule.get("distances", {}).get(str(circuit))
    return None
