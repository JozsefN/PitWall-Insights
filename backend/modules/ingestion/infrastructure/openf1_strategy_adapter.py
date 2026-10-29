"""Optional explicit enrichment. Never called by replay or strategy evaluation."""

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class OpenF1StrategyAdapter:
    base = "https://api.openf1.org/v1"

    def get(self, resource, **query):
        if resource not in ("sessions", "pit"):
            raise ValueError("Unsupported OpenF1 enrichment resource")
        request = Request(
            self.base + "/" + resource + "?" + urlencode(query),
            headers={"User-Agent": "PitWall-Insights-strategy-research/1.0"},
        )
        with urlopen(request, timeout=20) as response:
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError("OpenF1 enrichment response exceeds size limit")
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise ValueError("Expected an OpenF1 row list")
        return payload
