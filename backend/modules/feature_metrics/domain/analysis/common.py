import math
import heapq
import numpy as np
from .catalog import DEFINITIONS
from .models import AnalysisEvent, MetricValue


def json_safe(value):
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return round(value, 6) if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [json_safe(item) for item in value]
    return value


class Results:
    def __init__(self, request):
        self.request = request
        self.metrics = {}
        self._events = []
        self.total_events = 0

    @property
    def events(self):
        return [item[2] for item in self._events]

    def put(self, metric_id, value, entry=None, n=0, confidence=1.0, warnings=()):
        definition = DEFINITIONS[metric_id]
        value = json_safe(value)
        self.metrics[(metric_id, entry)] = MetricValue(
            metric_id=metric_id,
            entry_id=entry,
            value=value,
            unit=definition.unit,
            status=(
                "ok"
                if value is not None
                else "unavailable" if n == 0 else "insufficient_data"
            ),
            confidence=round(
                min(1, max(0, confidence)) if value is not None and n else 0, 3
            ),
            sample_count=int(n),
            warnings=list(warnings),
        )

    def missing(self, group, entry, reason):
        for definition in DEFINITIONS.values():
            if definition.group == group:
                self.put(definition.metric_id, None, entry, warnings=[reason])

    def event(
        self, kind, entry, start, end, confidence, classification="observed", **evidence
    ):
        if (
            self.request.event_kinds is not None
            and kind not in self.request.event_kinds
        ):
            return
        self.total_events += 1
        if not self.request.include_events or not self.request.max_events:
            return
        if (
            len(self._events) >= self.request.max_events
            and start >= -self._events[0][0]
        ):
            return
        event = AnalysisEvent(
            kind=kind,
            entry_id=entry,
            start_time_ms=int(start),
            end_time_ms=int(end),
            confidence=confidence,
            classification=classification,
            evidence=json_safe(evidence),
        )
        item = (-int(start), -self.total_events, event)
        if len(self._events) < self.request.max_events:
            heapq.heappush(self._events, item)
        else:
            heapq.heapreplace(self._events, item)


def numeric(rows, key):
    def number(value):
        try:
            return float(value) if value is not None else np.nan
        except (TypeError, ValueError):
            return np.nan

    return np.array([number(row.get(key)) for row in rows], dtype=float)


def stat(values, kind):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return None
    return {
        "mean": np.mean,
        "median": np.median,
        "min": np.min,
        "max": np.max,
        "std": np.std,
        "p95": lambda array: np.percentile(array, 95),
        "p90": lambda array: np.percentile(array, 90),
        "p10": lambda array: np.percentile(array, 10),
    }[kind](values).item()


def weights(times, start, end, max_gap_ms):
    times = np.asarray(times, dtype=float)
    if not len(times):
        return np.array([], dtype=float)
    gaps = np.diff(times)
    valid = gaps[(gaps > 0) & (gaps <= max_gap_ms)]
    tail = float(np.median(valid)) if len(valid) else 0
    next_times = np.r_[times[1:], times[-1] + tail]
    duration = np.maximum(0, np.minimum(next_times, end) - np.maximum(times, start))
    duration[(next_times - times > max_gap_ms) | (next_times <= times)] = 0
    return duration / 1000


def weighted_mean(values, duration):
    values = np.asarray(values, dtype=float)
    duration = np.asarray(duration, dtype=float)
    valid = np.isfinite(values) & (duration > 0)
    return (
        float(np.average(values[valid], weights=duration[valid]))
        if np.any(valid)
        else None
    )


def percentage(mask, duration, known=None):
    known = np.ones(len(duration), dtype=bool) if known is None else known
    denominator = float(np.sum(duration[known]))
    return (
        float(np.sum(duration[mask & known]) / denominator * 100)
        if denominator
        else None
    )


def episodes(mask, times, duration):
    active = np.asarray(mask, dtype=bool) & (duration > 0)
    if not len(active):
        return []
    starts = np.flatnonzero(active & ~np.r_[False, active[:-1]])
    ends = np.flatnonzero(active & ~np.r_[active[1:], False]) + 1
    return [
        (int(start), int(end), float(np.sum(duration[start:end])))
        for start, end in zip(starts, ends)
    ]


def selected_laps(entry, data, request, clean=False):
    laps = []
    for lap in entry.laps:
        start, end = lap.get("lap_start_time_ms"), lap.get("lap_end_time_ms")
        if start is None or end is None or start < data.start_ms or end > data.end_ms:
            continue
        number = lap["lap_number"]
        if request.lap_from is not None and number < request.lap_from:
            continue
        if request.lap_to is not None and number > request.lap_to:
            continue
        if clean and (
            not lap.get("is_accurate")
            or lap.get("is_deleted")
            or lap.get("is_generated")
            or lap.get("pit_in_time_ms") is not None
            or lap.get("pit_out_time_ms") is not None
            or lap.get("track_status") not in (None, "", "1")
            or not 10000 < float(lap.get("lap_time_ms") or 0) < 600000
        ):
            continue
        laps.append(lap)
    return sorted(laps, key=lambda lap: lap["lap_number"])


def pit_windows(entry):
    entries = sorted(
        {
            lap["pit_in_time_ms"]
            for lap in entry.laps
            if lap.get("pit_in_time_ms") is not None
        }
    )
    exits = sorted(
        {
            lap["pit_out_time_ms"]
            for lap in entry.laps
            if lap.get("pit_out_time_ms") is not None
        }
    )
    windows = []
    used_until = -1
    for start in entries:
        end = next((exit for exit in exits if exit > start and exit > used_until), None)
        if end is not None:
            windows.append((start, end))
            used_until = end
    return windows


def pit_mask(entry, times):
    mask = np.zeros(len(times), dtype=bool)
    for start, end in pit_windows(entry):
        mask |= (times >= start - 5000) & (times <= end + 5000)
    for lap in entry.laps:
        if (
            lap.get("pit_in_time_ms") is not None
            or lap.get("pit_out_time_ms") is not None
        ):
            start, end = lap.get("lap_start_time_ms"), lap.get("lap_end_time_ms")
            if start is not None and end is not None:
                mask |= (times >= start) & (times <= end)
    return mask


def neutralized_mask(data, times):
    result = np.zeros(len(times), dtype=bool)
    statuses = sorted(data.track_status, key=lambda row: row["session_time_ms"])
    for index, row in enumerate(statuses):
        end = (
            statuses[index + 1]["session_time_ms"]
            if index + 1 < len(statuses)
            else data.end_ms
        )
        if str(row.get("status")) != "1":
            result |= (times >= row["session_time_ms"]) & (times < end)
    return result


def car_arrays(entry, data, request):
    times = numeric(entry.car, "session_time_ms")
    duration = weights(
        times, data.start_ms, data.end_ms, request.options.max_sample_gap_ms
    )
    speed = numeric(entry.car, "speed_kph")
    speed[(speed < 0) | (speed > request.options.max_plausible_speed_kph)] = np.nan
    throttle = numeric(entry.car, "throttle_pct")
    throttle[(throttle < 0) | (throttle > 100)] = np.nan
    brake = numeric(entry.car, "brake_on")
    brake[~np.isin(brake, [0, 1])] = np.nan
    return times, duration, speed, throttle, brake


def aligned_values(rows, key, times, max_gap_ms):
    source_times = numeric(rows, "session_time_ms")
    values = numeric(rows, key)
    if len(rows) < 2:
        return np.full(len(times), np.nan)
    upper = np.clip(
        np.searchsorted(source_times, times, side="right"), 1, len(rows) - 1
    )
    lower = upper - 1
    valid = (
        (times >= source_times[0])
        & (times <= source_times[-1])
        & (source_times[upper] - source_times[lower] <= max_gap_ms)
    )
    valid &= (
        np.isfinite(values[upper])
        & np.isfinite(values[lower])
        & (source_times[upper] > source_times[lower])
    )
    output = np.full(len(times), np.nan)
    alpha = (times[valid] - source_times[lower[valid]]) / (
        source_times[upper[valid]] - source_times[lower[valid]]
    )
    output[valid] = values[lower[valid]] + alpha * (
        values[upper[valid]] - values[lower[valid]]
    )
    return output
