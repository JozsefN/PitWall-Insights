"""Build a compact public OpenF1 evidence archive. Run from backend with its venv."""

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from time import sleep
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import urlopen

from modules.feature_metrics.domain.review.intervention import (
    historical_episode,
    race_episodes,
)
from modules.feature_metrics.domain.source_clock import timed_rows


def get(resource, cache_dir=None, **filters):
    url = f"https://api.openf1.org/v1/{resource}?{urlencode(filters)}"
    cache = (
        cache_dir / (sha256(url.encode()).hexdigest() + ".json")
        if cache_dir and resource != "sessions"
        else None
    )
    if cache and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    for attempt in range(4):
        try:
            with urlopen(url, timeout=18) as stream:
                value = json.load(stream)
            if cache:
                cache.write_text(
                    json.dumps(value, separators=(",", ":")), encoding="utf-8"
                )
            return value
        except HTTPError as error:
            if error.code not in (429, 502, 503) or attempt == 3:
                raise
            delay = error.headers.get("Retry-After", "")
            sleep(
                min(70, int(delay))
                if delay.isdecimal()
                else (35 if error.code == 429 else 3)
            )
        except OSError:
            if attempt == 3:
                raise
            sleep(2 * (attempt + 1))


def build(years, only=None, cache_dir=None):
    history, covered, skipped = [], [], []
    for year in years:
        for race in get("sessions", year=year, session_name="Race"):
            if race.get("is_cancelled") or datetime.fromisoformat(
                race["date_end"]
            ) >= datetime.now(timezone.utc) - timedelta(minutes=30):
                continue
            key = race["session_key"]
            if only is not None and key not in only:
                continue
            try:
                controls = get("race_control", cache_dir, session_key=key)
                origin = datetime.fromisoformat(race["date_start"])
                end = datetime.fromisoformat(race["date_end"])
                rows = timed_rows(controls, origin)
                finish = next(
                    (
                        row["session_time_ms"]
                        for row in rows
                        if row["session_time_ms"] > 0 and row.get("flag") == "CHEQUERED"
                    ),
                    None,
                )
                if finish is None:
                    raise ValueError("No chequered flag establishes the coverage end")
                race["ended_epoch"] = max(
                    int(end.timestamp()), int(origin.timestamp() + finish / 1000)
                )
                episodes = race_episodes(rows, 0)
                history.extend(
                    historical_episode(episode, race, finish) for episode in episodes
                )
                covered.append(key)
                print(year, key, len(episodes), flush=True)
            except (OSError, KeyError, TypeError, ValueError) as error:
                skipped.append(key)
                print(year, key, str(error), flush=True)
            sleep(0.8)
    return {
        "source": "https://openf1.org/docs/#race-control",
        "version": 2,
        "seasons": list(years),
        "session_keys": covered,
        "skipped_session_keys": skipped,
        "episodes": history,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--missing",
        action="store_true",
        help="Retry only skipped sessions in the existing archive",
    )
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=list(range(2023, 2027))
    )
    parser.add_argument("--cache-dir", type=Path)
    options = parser.parse_args()
    path = Path(__file__).resolve().parents[2] / "shared" / "intervention-history.json"
    prior = json.loads(path.read_text(encoding="utf-8")) if options.missing else None
    years = prior["seasons"] if prior else options.seasons
    if options.cache_dir:
        options.cache_dir.mkdir(parents=True, exist_ok=True)
    archive = build(
        years, set(prior["skipped_session_keys"]) if prior else None, options.cache_dir
    )
    if prior:
        archive["session_keys"] = sorted(
            set(prior["session_keys"]) | set(archive["session_keys"])
        )
        archive["episodes"] = sorted(
            [*prior["episodes"], *archive["episodes"]],
            key=lambda row: row["available_after"],
        )
    if len(archive["session_keys"]) < 40:
        raise SystemExit("Insufficient covered races to replace the archive")
    path.write_text(json.dumps(archive, separators=(",", ":")) + "\n", encoding="utf-8")
