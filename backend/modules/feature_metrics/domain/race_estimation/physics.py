"""Airflow and brake onset components for the race model."""

import math
from statistics import median

from .common import is_clean


def put_weather(conditions, request, current, heading, result):
    for key in (
        "air_density_kgm3",
        "air_temperature_c",
        "track_temperature_c",
        "wind_speed_ms",
    ):
        result.put(key, conditions.get(key), 0.65)
    wind = conditions.get("wind_speed_ms")
    if current is not None and wind is not None:
        speed = current["speed_kph"] / 3.6
        result.put("relative_air_speed_low_kph", max(0, speed - wind) * 3.6, 0.4)
        result.put("relative_air_speed_high_kph", (speed + wind) * 3.6, 0.4)
    config = request.assumptions
    direction = conditions.get("wind_direction_deg")
    if (
        current is not None
        and heading is not None
        and config.north_rotation_deg is not None
        and config.wind_direction_is_from is not None
        and wind is not None
        and direction is not None
    ):
        bearing = math.pi / 2 - heading + math.radians(config.north_rotation_deg)
        direction_from = math.radians(direction) + (
            0 if config.wind_direction_is_from else math.pi
        )
        headwind = wind * math.cos(direction_from - bearing)
        crosswind = wind * math.sin(direction_from - bearing)
        relative = math.hypot(current["speed_kph"] / 3.6 + headwind, crosswind)
        result.put("headwind_ms", headwind, 0.35)
        result.put("crosswind_ms", crosswind, 0.35)
        result.put("relative_air_speed_kph", relative * 3.6, 0.35)
        if current["speed_kph"] >= 40:
            result.put(
                "wind_pressure_shift_pct",
                100 * ((relative * 3.6 / current["speed_kph"]) ** 2 - 1),
                0.3,
                reason="Dynamic pressure changes with airspeed squared; car aero coefficients and any lap-time effect remain unknown.",
            )
    else:
        result.put(
            "headwind_ms",
            None,
            reason="XYZ north alignment and wind FROM/TO convention must both be explicitly calibrated.",
        )
    rho = conditions.get("air_density_kgm3")
    if current is not None and rho is not None:
        relative = result.metrics["relative_air_speed_kph"].value
        speed = current["speed_kph"] / 3.6
        airspeed = relative / 3.6 if isinstance(relative, (int, float)) else speed
        result.put(
            "dynamic_pressure_pa",
            0.5 * rho * airspeed**2,
            0.35,
            lower=0.5 * rho * max(0, speed - wind) ** 2 if wind is not None else None,
            upper=0.5 * rho * (speed + wind) ** 2 if wind is not None else None,
            reason="Air density uses the dry-air ideal-gas approximation. Central airspeed uses the ground-speed proxy unless wind alignment is calibrated; bounds reflect unknown wind angle.",
        )


def put_brake_shift(entry, data, request, zones, rows, result):
    if data.reference is None or len(zones) < 2:
        return
    length = data.reference.length
    scales = []
    for lap in entry.laps:
        if not is_clean(lap):
            continue
        begin, end = lap.get("lap_start_time_ms"), lap.get("lap_end_time_ms")
        if begin is None or end is None or end > request.as_of_ms:
            continue
        samples = [r for r in rows if begin <= r["session_time_ms"] <= end]
        elapsed = distance = 0.0
        for a, b in zip(samples, samples[1:]):
            dt = (b["session_time_ms"] - a["session_time_ms"]) / 1000
            if 0 < dt <= request.assumptions.max_telemetry_gap_ms / 1000:
                elapsed += dt
                distance += (a["speed_kph"] + b["speed_kph"]) / 2 / 3.6 * dt
        if (
            elapsed >= 0.85 * (end - begin) / 1000
            and length > 0
            and 0.3 <= distance / length <= 3
        ):
            scales.append(distance / length)
    # A reference-scale cross-check uses observed lap speed integration where possible.
    factor = (
        median(scales)
        if scales
        else request.assumptions.position_scale_m_per_unit / 0.1
    )
    latest = zones[-1]
    if latest["progress_pct"] is None:
        return
    matches = [
        zone
        for zone in zones[:-1]
        if zone["progress_pct"] is not None
        and latest["start_ms"] - zone["start_ms"] >= 20000
        and abs((latest["progress_pct"] - zone["progress_pct"] + 50) % 100 - 50) < 3
    ]
    if matches:
        baseline = matches[-1]
        shift = (
            ((latest["progress_pct"] - baseline["progress_pct"] + 50) % 100 - 50)
            / 100
            * length
            * factor
        )
        result.put(
            "brake_point_shift_m",
            shift,
            0.5 if scales else 0.25,
            lower=shift - 10,
            upper=shift + 10,
            reason=(
                "Same approximate map location; speed-integral scale cross-check."
                if scales
                else "Uses an unverified coordinate-scale assumption and approximate source positions."
            ),
        )
