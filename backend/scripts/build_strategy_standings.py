"""Archive pre-race standings for strategy without importing post-race points."""

from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from urllib.error import HTTPError

from .build_intervention_archive import get


def standings_archive(years):
    output, unavailable = {}, []
    for year in years:
        keys = {
            row["session_key"]
            for row in get("sessions", year=year, session_name="Race")
            if not row.get("is_cancelled")
            and datetime.fromisoformat(row["date_end"])
            < datetime.now(timezone.utc) - timedelta(minutes=30)
        }
        if not keys:
            continue
        try:
            standings = get(
                "championship_drivers",
                **{"session_key>": min(keys), "session_key<": max(keys)}
            )
        except HTTPError as error:
            if error.code != 404:
                raise
            standings = []
        for row in standings:
            if row["session_key"] in keys and row.get("position_start") is not None:
                output.setdefault(str(row["session_key"]), {})[
                    str(row["driver_number"])
                ] = [row["position_start"], row.get("points_start")]
        unavailable.extend(sorted(key for key in keys if str(key) not in output))
        print(year, len(keys), sum(str(key) in output for key in keys), flush=True)
    return {
        "source": "https://openf1.org/docs/#drivers-championship-beta",
        "races": output,
        "unavailable_races": unavailable,
    }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=list(range(2023, 2027))
    )
    options = parser.parse_args()
    archive = standings_archive(options.seasons)
    if not archive["races"]:
        raise SystemExit("No standings received. The existing archive was preserved.")
    path = Path(__file__).resolve().parents[2] / "shared/strategy-standings.json"
    path.write_text(json.dumps(archive, separators=(",", ":")) + "\n", encoding="utf-8")
