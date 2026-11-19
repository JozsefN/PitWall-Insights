import hashlib
import math
from bisect import bisect_right
from statistics import median

from .catalog import DEFINITIONS
from .models import EstimateValue, RaceEvent

G = 9.80665


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def clamp(value, lo=0.0, hi=1.0):
    return min(hi, max(lo, value))


def at(rows, time_ms, max_age=None):
    if not rows:
        return None
    index = bisect_right([row["session_time_ms"] for row in rows], time_ms) - 1
    if index < 0:
        return None
    row = rows[index]
    return (
        row if max_age is None or time_ms - row["session_time_ms"] <= max_age else None
    )


class Cursor:
    """Linear-time, causal as-of join for ascending observation clocks."""

    def __init__(self, rows):
        self.rows = sorted(rows, key=lambda row: row["session_time_ms"])
        self.index = -1

    def get(self, time_ms, max_age=None):
        while (
            self.index + 1 < len(self.rows)
            and self.rows[self.index + 1]["session_time_ms"] <= time_ms
        ):
            self.index += 1
        if self.index < 0:
            return None
        row = self.rows[self.index]
        return (
            row
            if max_age is None or time_ms - row["session_time_ms"] <= max_age
            else None
        )


def number(value):
    if finite(value):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value)
            return parsed if math.isfinite(parsed) else None
        except ValueError:
            return None
    return None


def slope(points):
    """Least squares on relative seconds to retain timestamp precision."""
    if len(points) < 3:
        return None
    origin = points[0][0]
    xs = [(p[0] - origin) / 1000 for p in points]
    ys = [p[1] for p in points]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def robust_slope(points):
    slopes = [
        (y1 - y0) / (x1 - x0)
        for i, (x0, y0) in enumerate(points)
        for x1, y1 in points[i + 1 :]
        if x1 > x0
    ]
    return median(slopes) if slopes else None


def is_clean(lap):
    return (
        bool(lap.get("is_accurate"))
        and not any(lap.get(key) for key in ("is_generated", "is_deleted"))
        and all(lap.get(key) is None for key in ("pit_in_time_ms", "pit_out_time_ms"))
        and str(lap.get("track_status") or "") == "1"
        and finite(lap.get("lap_time_ms"))
        and lap["lap_time_ms"] > 0
    )


class Values:
    def __init__(self):
        self.metrics = {
            key: EstimateValue(
                unit=d["unit"],
                method=d["method"],
                status="unavailable",
                reason="Required observations or comparable context are unavailable.",
            )
            for key, d in DEFINITIONS.items()
        }

    def put(
        self,
        key,
        value,
        support=1.0,
        *,
        lower=None,
        upper=None,
        reason=None,
        unavailable_cause=None,
    ):
        definition = DEFINITIONS[key]
        if value is None or isinstance(value, (int, float)) and not finite(value):
            if reason:
                self.metrics[key].reason = reason
            self.metrics[key].unavailable_cause = unavailable_cause
            return
        lower = float(lower) if finite(lower) else None
        upper = float(upper) if finite(upper) else None
        self.metrics[key] = EstimateValue(
            value=round(float(value), 6) if finite(value) else str(value),
            unit=definition["unit"],
            method=definition["method"],
            support=clamp(support),
            reason=reason,
            lower=lower,
            upper=upper,
            uncertainty=(
                "sensitivity_range" if lower is not None and upper is not None else None
            ),
        )


def event(
    kind,
    entry_id,
    start,
    observed_at,
    title,
    detail,
    *,
    support=0.5,
    severity="watch",
    classification="candidate",
    rival=None,
    evidence=None,
    alternatives=None,
):
    key = f"{kind}|{entry_id}|{rival}|{start}"
    return RaceEvent(
        id=hashlib.sha256(key.encode()).hexdigest()[:24],
        kind=kind,
        entry_id=entry_id,
        rival_entry_id=rival,
        start_ms=int(start),
        time_ms=int(observed_at),
        title=title,
        detail=detail,
        support=clamp(support),
        severity=severity,
        classification=classification,
        evidence=evidence or {},
        alternatives=alternatives or [],
    )


def phase_at(rows, time_ms):
    row = at(rows, time_ms)
    return str(row.get("status")) if row else "unknown"


def in_pit(entry, time_ms, context):
    entries = [
        (lap.get(key), key)
        for lap in entry.laps
        for key in ("pit_in_time_ms", "pit_out_time_ms")
        if finite(lap.get(key)) and lap[key] <= time_ms
    ]
    if entries and max(entries)[1] == "pit_in_time_ms":
        return True
    # A native report is evidence of a recent pit visit, not a fabricated pit-in timestamp.
    return any(
        row.get("driver_number") == entry.car_number
        and 0 <= time_ms - row.get("known_at_ms", row["session_time_ms"]) <= 15000
        for row in context.pits
    )


def conditions_at(data, request):
    weather = at(data.weather, request.as_of_ms, 120000)
    result = {
        "track_status": phase_at(data.track_status, request.as_of_ms),
        "weather_age_s": None,
        "air_temperature_c": None,
        "track_temperature_c": None,
        "wind_speed_ms": None,
        "wind_direction_deg": None,
        "air_density_kgm3": None,
        "rain_reported": None,
    }
    if weather:
        result.update(
            weather_age_s=(request.as_of_ms - weather["session_time_ms"]) / 1000,
            air_temperature_c=number(weather.get("air_temp_c")),
            track_temperature_c=number(weather.get("track_temp_c")),
            wind_speed_ms=(
                number(weather.get("wind_speed_kph")) / 3.6
                if number(weather.get("wind_speed_kph")) is not None
                else None
            ),
            wind_direction_deg=number(weather.get("wind_direction_deg")),
            rain_reported=weather.get("rainfall"),
        )
        temp = result["air_temperature_c"]
        pressure = number(weather.get("pressure_mbar"))
        if (
            pressure is not None
            and temp is not None
            and 500 <= pressure <= 1100
            and -30 <= temp <= 60
        ):
            result["air_density_kgm3"] = pressure * 100 / (287.05 * (temp + 273.15))
    return result
