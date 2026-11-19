"""Venue metadata shared with the maps and session artwork."""

import json
from pathlib import Path


_catalog = json.loads(
    (Path(__file__).resolve().parents[4] / "shared" / "circuit-catalog.json").read_text(encoding="utf-8")
)
_hosts_by_openf1_key = {
    str(row["openf1Key"]): _catalog["hosts"][row["host"]]["name"]
    for row in _catalog["circuits"]
}


def openf1_host_country(circuit_key: int | str | None) -> str | None:
    return _hosts_by_openf1_key.get(str(circuit_key))
