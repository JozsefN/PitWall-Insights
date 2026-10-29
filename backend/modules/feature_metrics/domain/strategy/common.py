import numpy as np
from .catalog import DEFINITIONS
from .models import StrategyValue, Bounds
from modules.feature_metrics.domain.analysis.common import json_safe


class Values:
    def __init__(self, as_of):
        self.as_of = as_of
        self.values = {}

    def put(
        self,
        key,
        value,
        entry=None,
        rival=None,
        *,
        status="derived",
        n=0,
        bounds=None,
        support=None,
        warnings=()
    ):
        definition = DEFINITIONS[key]
        value = json_safe(value)
        self.values[(key, entry, rival)] = StrategyValue(
            metric_id=key,
            entry_id=entry,
            rival_entry_id=rival,
            value=value,
            unit=definition.unit,
            status=status if value is not None else "unavailable",
            sample_count=n,
            as_of_ms=self.as_of,
            bounds=bounds,
            support=json_safe(support or {}),
            warnings=list(warnings),
        )

    def fill(self, entry, rivals):
        for definition in DEFINITIONS.values():
            for rival in rivals if definition.scope == "pair" else [None]:
                target = None if definition.scope == "session" else entry
                key = (definition.metric_id, target, rival)
                if key not in self.values:
                    self.put(
                        definition.metric_id,
                        None,
                        target,
                        rival,
                        warnings=[
                            "Required input/model is unavailable; see readiness and catalogue."
                        ],
                    )

    def get(self, key, entry, rival=None):
        item = self.values.get((key, entry, rival))
        return item.value if item is not None else None


def clean_laps(entry, as_of):
    return sorted(
        [
            row
            for row in entry.laps
            if row.get("lap_end_time_ms") is not None
            and row["lap_end_time_ms"] <= as_of
            and row.get("is_accurate")
            and not row.get("is_deleted")
            and not row.get("is_generated")
            and row.get("pit_in_time_ms") is None
            and row.get("pit_out_time_ms") is None
            and row.get("track_status") == "1"
            and 10000 < (row.get("lap_time_ms") or 0) < 600000
        ],
        key=lambda row: row["lap_number"],
    )


def mad(values):
    return (
        float(1.4826 * np.median(np.abs(np.asarray(values) - np.median(values))))
        if len(values)
        else None
    )


def slope(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 3:
        return None
    dx = x[None, :] - x[:, None]
    dy = y[None, :] - y[:, None]
    valid = np.triu(np.ones(dx.shape, dtype=bool), 1) & (dx > 0)
    return float(np.median(dy[valid] / dx[valid])) if np.any(valid) else None


def phase_at(data, time):
    rows = [row for row in data.track_status if row["session_time_ms"] <= time]
    return (
        str(max(rows, key=lambda row: row["session_time_ms"])["status"])
        if rows
        else None
    )


def clear_interval(data, start, end):
    return phase_at(data, start) == "1" and all(
        str(row["status"]) == "1"
        for row in data.track_status
        if start < row["session_time_ms"] <= end
    )


def band(value, error, meaning="sensitivity_range"):
    return Bounds(
        lower=float(value - error), upper=float(value + error), meaning=meaning
    )
