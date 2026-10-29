"""Conservative geometry and relative-air physics; no invented geographic alignment."""

import math
import numpy as np
from modules.feature_metrics.domain.analysis.common import numeric
from .common import phase_at


def polygon_area(points):
    points = np.asarray(points, dtype=float)
    following = np.roll(points, -1, axis=0)
    return float(
        np.sum(points[:, 0] * following[:, 1] - following[:, 0] * points[:, 1]) / 2
    )


def polygon_clearance(point, polygon):
    point = np.asarray(point, dtype=float)
    p = np.asarray(polygon, dtype=float)
    q = np.roll(p, -1, axis=0)
    vector = q - p
    length = np.sum(vector * vector, axis=1)
    alpha = np.clip(
        np.sum((point - p) * vector, axis=1) / np.maximum(length, 1e-12), 0, 1
    )
    distance = float(
        np.min(np.linalg.norm(p + alpha[:, None] * vector - point, axis=1))
    )
    crossings = (p[:, 1] > point[1]) != (q[:, 1] > point[1])
    intercept = p[:, 0] + (point[1] - p[:, 1]) * (q[:, 0] - p[:, 0]) / np.where(
        q[:, 1] != p[:, 1], q[:, 1] - p[:, 1], 1
    )
    inside = bool(np.sum(crossings & (point[0] < intercept)) % 2)
    return distance if inside else -distance


def motion(entry, data, request, context, result):
    cutoff = request.as_of_ms
    car = [row for row in entry.car if row["session_time_ms"] <= cutoff]
    positions = [row for row in entry.positions if row["session_time_ms"] <= cutoff]
    point = None
    heading = None
    turn = None
    fresh_position = bool(
        positions and cutoff - positions[-1]["session_time_ms"] <= 2000
    )
    if fresh_position:
        row = positions[-1]
        xy = numeric([row], "x")[0], numeric([row], "y")[0]
        if all(math.isfinite(value) for value in xy) and any(xy):
            point = np.array(xy) * 0.1
        if point is not None and len(positions) >= 2:
            prior = positions[-2]
            elapsed = (row["session_time_ms"] - prior["session_time_ms"]) / 1000
            previous = np.array([prior.get("x"), prior.get("y")], dtype=float) * 0.1
            if (
                0 < elapsed <= 2
                and np.all(np.isfinite(previous))
                and np.linalg.norm(point - previous) / elapsed * 3.6 > 450
            ):
                point = None
                fresh_position = False
    fresh_car = bool(car and cutoff - car[-1]["session_time_ms"] <= 2000)
    speed = car[-1].get("speed_kph") if fresh_car else None
    if speed is not None and (not math.isfinite(speed) or not 0 <= speed <= 450):
        speed = None
    headings = []
    for a, b in list(zip(positions[:-1], positions[1:]))[-2:]:
        dt = (b["session_time_ms"] - a["session_time_ms"]) / 1000
        xy = (
            np.array([[a.get("x"), a.get("y")], [b.get("x"), b.get("y")]], dtype=float)
            * 0.1
        )
        if np.all(np.isfinite(xy)) and np.all(np.any(xy != 0, axis=1)) and 0 < dt <= 2:
            delta = xy[1] - xy[0]
            distance = np.linalg.norm(delta)
            if 0.5 < distance <= 450 / 3.6 * dt:
                headings.append(math.atan2(delta[1], delta[0]))
            else:
                headings = []
        else:
            headings = []
    if fresh_position and headings:
        heading = headings[-1]
        if len(headings) == 2:
            angle = (headings[1] - headings[0] + math.pi) % (2 * math.pi) - math.pi
            turn = "left" if angle > 0.01 else "right" if angle < -0.01 else "straight"
    result.put(
        "vehicle_heading_xy_deg",
        math.degrees(heading) % 360 if heading is not None else None,
        entry.id,
        n=len(headings),
        status="estimated",
    )
    result.put(
        "vehicle_turn_direction", turn, entry.id, n=len(headings), status="estimated"
    )
    stop = 0.0
    if fresh_car and speed is not None and speed <= 5:
        first = car[-1]["session_time_ms"]
        for prior, next_row in reversed(list(zip(car[:-1], car[1:]))):
            value = prior.get("speed_kph")
            if (
                value is None
                or not math.isfinite(value)
                or not 0 <= value <= 5
                or not 0
                < next_row["session_time_ms"] - prior["session_time_ms"]
                <= 2000
            ):
                break
            first = prior["session_time_ms"]
        stop = (car[-1]["session_time_ms"] - first) / 1000
    recent = [row for row in car if row["session_time_ms"] >= cutoff - 30000]
    times = numeric(recent, "session_time_ms")
    speeds = numeric(recent, "speed_kph")
    drop = 0.0
    run_start = 0
    drop_end = None
    for i in range(len(times)):
        if not np.isfinite(speeds[i]) or not 0 <= speeds[i] <= 450:
            run_start = i + 1
            continue
        if i and (times[i] - times[i - 1] > 2000 or not np.isfinite(speeds[i - 1])):
            run_start = i
        left = max(run_start, int(np.searchsorted(times, times[i] - 2000)))
        if left < i:
            change = float(np.max(speeds[left:i]) - speeds[i])
            if change > drop:
                drop = change
                drop_end = times[i]
    pit_in = max(
        (
            row["pit_in_time_ms"]
            for row in entry.laps
            if row.get("pit_in_time_ms") is not None and row["pit_in_time_ms"] <= cutoff
        ),
        default=-1,
    )
    pit_out = max(
        (
            row["pit_out_time_ms"]
            for row in entry.laps
            if row.get("pit_out_time_ms") is not None
            and row["pit_out_time_ms"] <= cutoff
        ),
        default=-1,
    )
    in_pit = pit_in > pit_out
    clearance = None
    recovery = None
    surface = "unknown"
    recovery_access = "unknown"
    track = context.track if context else None
    if point is not None and track:
        zones = [zone for zone in track.zones if zone.kind == "racing_surface"]
        if zones:
            clearance = max(polygon_clearance(point, zone.polygon_m) for zone in zones)
            surface = (
                "on_track"
                if clearance > track.position_error_m
                else "off_track" if clearance < -track.position_error_m else "unknown"
            )
        if track.recovery_points_m:
            recovery = float(
                np.min(
                    np.linalg.norm(np.asarray(track.recovery_points_m) - point, axis=1)
                )
            )
            recovery_access = (
                "near"
                if recovery + track.position_error_m < 50
                else "far" if recovery - track.position_error_m > 50 else "unknown"
            )
        in_pit = in_pit or any(
            polygon_clearance(point, zone.polygon_m) > track.position_error_m
            for zone in track.zones
            if zone.kind == "pit_lane"
        )
    state = (
        "stale"
        if point is None or speed is None
        else (
            "pit"
            if in_pit
            else (
                "stopped_in_recovery_zone"
                if stop >= 4 and surface == "off_track" and recovery_access == "near"
                else (
                    "stationary_on_track"
                    if stop >= 4 and surface == "on_track"
                    else (
                        "stationary_off_track"
                        if stop >= 4 and surface == "off_track"
                        else (
                            "stationary_unknown_surface"
                            if stop >= 4
                            else "slow_running" if speed < 60 else "moving"
                        )
                    )
                )
            )
        )
    )
    collision = bool(
        drop >= 100
        and stop >= 4
        and drop_end is not None
        and drop_end >= car[-1]["session_time_ms"] - stop * 1000 - 5000
        and not in_pit
    )
    retirement = bool(stop >= 30 and surface == "off_track" and not in_pit)
    result.put(
        "incident_max_short_drop_kph",
        drop if len(recent) > 1 else None,
        entry.id,
        n=len(recent),
        status="observed",
    )
    result.put(
        "incident_current_stop_duration_s",
        stop if fresh_car and speed is not None else None,
        entry.id,
        n=len(car),
        status="observed",
    )
    result.put(
        "incident_motion_state",
        state,
        entry.id,
        status="estimated",
        support={
            "surface": surface,
            "recovery_access": recovery_access,
            "fresh_position": fresh_position,
            "fresh_car": fresh_car,
        },
    )
    result.put(
        "incident_surface_clearance_m",
        clearance,
        entry.id,
        status="estimated",
        warnings=[
            "Conservative polygon clearance; position error band applies, not an official track-limits ruling."
        ],
    )
    result.put("incident_nearest_recovery_m", recovery, entry.id, status="estimated")
    result.put(
        "incident_candidate_collision",
        collision if fresh_car and point is not None else None,
        entry.id,
        status="estimated",
        warnings=[
            "Ordinary braking, mechanical failure and controlled stopping can produce similar signals."
        ],
    )
    result.put(
        "incident_retirement_candidate",
        retirement if point is not None and fresh_car else None,
        entry.id,
        status="estimated",
    )
    return dict(
        point=point,
        heading=heading,
        speed=speed,
        stopped=stop >= 4,
        stop_duration_s=stop,
        surface=surface,
        recovery_access=recovery_access,
        in_pit=in_pit,
        state=state,
        collision=collision,
    )


def wind_physics(entry, data, request, context, state, result):
    rows = [row for row in data.weather if row["session_time_ms"] <= request.as_of_ms]
    weather = max(rows, key=lambda row: row["session_time_ms"]) if rows else None
    if weather is None or request.as_of_ms - weather["session_time_ms"] > 180000:
        return
    temperature = weather.get("air_temp_c")
    pressure = weather.get("pressure_mbar")
    humidity = weather.get("humidity_pct")
    rho = None
    if (
        temperature is not None
        and pressure is not None
        and humidity is not None
        and -50 <= temperature <= 70
        and 500 <= pressure <= 1100
        and 0 <= humidity <= 100
    ):
        kelvin = temperature + 273.15
        vapour = (
            humidity
            / 100
            * 611.2
            * math.exp(17.67 * temperature / (temperature + 243.5))
        )
        rho = (pressure * 100 - vapour) / (287.05 * kelvin) + vapour / (
            461.495 * kelvin
        )
    result.put(
        "weather_moist_air_density_kg_m3", rho, entry.id, status="estimated", n=1
    )
    track = context.track if context else None
    if (
        track is None
        or track.north_angle_xy_deg is None
        or track.alignment_error_deg > 10
        or state["heading"] is None
        or state["speed"] is None
    ):
        return
    wind = weather.get("wind_speed_kph")
    direction = weather.get("wind_direction_deg")
    if (
        wind is None
        or direction is None
        or not 0 <= wind <= 300
        or not 0 <= direction <= 360
    ):
        return
    alpha = math.radians(track.north_angle_xy_deg)
    bearing = math.radians(direction)
    north = np.array([math.cos(alpha), math.sin(alpha)])
    east = np.array([math.sin(alpha), -math.cos(alpha)])
    wind_vector = -wind / 3.6 * (math.sin(bearing) * east + math.cos(bearing) * north)
    heading = state["heading"]
    forward = np.array([math.cos(heading), math.sin(heading)])
    right = np.array([math.sin(heading), -math.cos(heading)])
    ground = state["speed"] / 3.6
    relative = ground * forward - wind_vector
    air = float(np.linalg.norm(relative))
    head = -float(wind_vector @ forward)
    cross = float(wind_vector @ right)
    values = {
        "weather_headwind_mps": head,
        "weather_crosswind_right_mps": cross,
        "weather_relative_air_speed_mps": air,
        "weather_relative_air_yaw_deg": math.degrees(
            math.atan2(float(relative @ right), float(relative @ forward))
        ),
        "weather_dynamic_pressure_pa": 0.5 * rho * air**2 if rho is not None else None,
        "weather_dynamic_pressure_change_pct": (
            100 * (air**2 / ground**2 - 1) if ground > 5 else None
        ),
    }
    for key, value in values.items():
        result.put(
            key,
            value,
            entry.id,
            status="estimated",
            n=1,
            support={
                "weather_age_s": (request.as_of_ms - weather["session_time_ms"]) / 1000,
                "alignment_error_deg": track.alignment_error_deg,
            },
            warnings=[
                "Station weather is not local airflow. Dynamic pressure is not lap-time loss; aero coefficients are unavailable."
            ],
        )
