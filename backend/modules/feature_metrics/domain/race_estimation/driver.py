"""Driver dynamics, exposure and pace. All accumulators consume past observations only."""

import math
from statistics import median
import numpy as np

from .common import (
    G,
    Cursor,
    Values,
    clamp,
    finite,
    number,
    is_clean,
    in_pit,
    phase_at,
    robust_slope,
    event,
)
from .traffic import wake_loss
from .physics import put_weather, put_brake_shift
from .models import DriverEstimate
from .braking import plateau_step, PLATEAU_DURATION_MS, PLATEAU_SAMPLE_COUNT


def evaluate_driver(
    entry, data, context, request, traffic_samples, traffic, conditions
):
    config = request.assumptions
    result = Values()
    start = max(data.start_ms, request.as_of_ms - request.lookback_ms)
    rows = sorted(
        (
            r
            for r in entry.car
            if start <= r["session_time_ms"] <= request.as_of_ms
            and finite(r.get("speed_kph"))
            and 0 <= r["speed_kph"] <= 450
        ),
        key=lambda r: r["session_time_ms"],
    )
    positions = Cursor(entry.positions)
    lap_starts = [
        lap["lap_start_time_ms"]
        for lap in entry.laps
        if finite(lap.get("lap_start_time_ms"))
    ]
    race_start = min(lap_starts) if lap_starts else None
    session_end = min(
        (
            row["session_time_ms"]
            for row in data.race_control
            if "SESSION FINISHED" in str(row.get("message", "")).upper()
            or "CHEQUERED" in str(row.get("flag", "")).upper()
        ),
        default=None,
    )
    events, series, zones = [], [], []
    seconds = traffic_seconds = close_seconds = lap_traffic = tow_seconds = (
        corner_traffic
    ) = neutralised = 0.0
    gap_seconds = brake_seconds = full_seconds = drs_seconds = coast_seconds = 0.0
    energy = decel_sum = decel_seconds = peak_decel = corner_sum = traction_sum = (
        extra_work
    ) = 0.0
    thermal = 0.0
    geometry_seconds = 0.0
    gap_integral = distance_integral = 0.0
    wake_corner_integral = 0.0
    previous = None
    previous_pos = None
    heading = None
    lateral_history = []
    last_lateral = last_wake = last_gap = None
    last_accel = None
    current_zone = None
    brake_release = None
    recoveries = []
    plateau_start = None
    plateau_n = 0
    plateau_emitted = False
    stop_start = None
    stop_samples = 0
    stop_emitted = False
    incident_emitted = False
    rpm_emitted_until = -1
    end_traffic = traffic_samples.get(request.as_of_ms, {})
    ahead = end_traffic.get(entry.car_number, {})
    entry_reports = sorted(
        traffic.intervals.get(entry.car_number, []), key=lambda r: r["session_time_ms"]
    )
    report_cursor = Cursor(entry_reports)
    pressure_started = None
    pressure_notified = False
    phase_rows = data.track_status

    def finish_zone():
        nonlocal current_zone
        if current_zone and current_zone["duration_s"] >= 0.25:
            zones.append(current_zone)
        current_zone = None

    def progress_at(row):
        if data.reference is None or row is None:
            return None
        if not finite(row.get("x")) or not finite(row.get("y")):
            return None
        try:
            error, along = data.reference.project(
                np.array([[row["x"] * 0.1, row["y"] * 0.1]], dtype=float)
            )
            return float(along[0]) if error[0] < 30 else None
        except (ValueError, TypeError):
            return None

    for row in rows:
        t = row["session_time_ms"]
        speed = row["speed_kph"]
        dt = (t - previous["session_time_ms"]) / 1000 if previous else 0.0
        continuous = (
            previous is not None and 0 < dt <= config.max_telemetry_gap_ms / 1000
        )
        if not continuous:
            finish_zone()
            plateau_start = stop_start = None
            plateau_n = stop_samples = 0
            plateau_emitted = stop_emitted = incident_emitted = False
            previous_pos = None
            heading = None
            lateral_history = []
        weight = dt if continuous else 0.0
        seconds += weight
        brake = row.get("brake_on") is True
        throttle = number(row.get("throttle_pct"))
        pos = positions.get(t, config.max_telemetry_gap_ms)
        lateral = None
        if pos and pos is not previous_pos and previous_pos:
            pdt = (pos["session_time_ms"] - previous_pos["session_time_ms"]) / 1000
            if all(finite(p.get(k)) for p in (pos, previous_pos) for k in ("x", "y")):
                dx = (pos["x"] - previous_pos["x"]) * config.position_scale_m_per_unit
                dy = (pos["y"] - previous_pos["y"]) * config.position_scale_m_per_unit
                distance = math.hypot(dx, dy)
                if (
                    0 < pdt <= config.max_telemetry_gap_ms / 1000
                    and 2 < distance <= max(50, 4 * speed / 3.6 * pdt)
                ):
                    next_heading = math.atan2(dy, dx)
                    if heading is not None and speed >= 40:
                        turn = math.atan2(
                            math.sin(next_heading - heading),
                            math.cos(next_heading - heading),
                        )
                        value = speed / 3.6 * abs(turn) / pdt / G
                        if value <= 6:
                            lateral_history.append(value)
                            lateral = median(lateral_history[-3:])
                    heading = next_heading
        if pos and pos is not previous_pos:
            previous_pos = pos
        phase = phase_at(phase_rows, t)
        racing = (
            race_start is not None
            and t >= race_start
            and (session_end is None or t < session_end)
        )
        pit = in_pit(entry, t, context)
        green = phase == "1" and racing and not pit
        geometry_seconds += weight * (green and lateral is not None)
        neutralised += weight * (not green)
        report = report_cursor.get(
            t - config.source_report_delay_ms, config.max_report_age_ms
        )
        gap = number(report.get("interval")) if report else None
        if gap is not None and not 0 <= gap <= 120:
            gap = None
        if traffic_samples.get(t, {}).get(entry.car_number, {}).get("rank") == 1:
            gap = None
        if gap is not None:
            gap_integral += weight * gap
            distance_integral += weight * gap * speed / 3.6
        lapped = (
            report is not None
            and isinstance(report.get("interval"), str)
            and "lap" in report["interval"].lower()
        )
        # A numeric interval without sufficient rank evidence remains a headway report;
        # car identity is only attached from the native rank context.
        gap_seconds += weight * (gap is not None)
        lap_traffic += weight * bool(lapped)
        following = green and gap is not None and 0 < gap <= config.traffic_gap_s
        close = following and gap <= config.close_gap_s
        traffic_seconds += weight * following
        close_seconds += weight * close
        wake = (
            wake_loss(gap * speed / 3.6, config) if following and speed >= 40 else 0.0
        )
        turning = lateral is not None and lateral > 0.5
        straight = lateral is not None and lateral < 0.25
        corner_traffic += weight * (following and turning)
        tow_seconds += weight * (following and straight and speed >= 180)
        accel = (speed - previous["speed_kph"]) / 3.6 / dt / G if continuous else None
        if accel is not None and abs(accel) > 8:
            accel = None
        last_accel = accel
        if brake and continuous:
            brake_seconds += weight
            decel = max(0, -accel) if accel is not None else 0.0
            peak_decel = max(peak_decel, decel)
            decel_sum += decel * weight
            decel_seconds += weight
            kinetic = (
                max(0, 0.5 * ((previous["speed_kph"] / 3.6) ** 2 - (speed / 3.6) ** 2))
                / 1000
            )
            energy += kinetic
            if current_zone is None and speed >= 40:
                current_zone = {
                    "start_ms": t,
                    "end_ms": t,
                    "duration_s": 0.0,
                    "entry_speed_kph": previous["speed_kph"],
                    "exit_speed_kph": speed,
                    "peak_deceleration_g": 0.0,
                    "kinetic_loss_kjkg": 0.0,
                    "progress_pct": progress_at(pos),
                }
            if current_zone:
                current_zone.update(
                    end_ms=t,
                    duration_s=current_zone["duration_s"] + weight,
                    exit_speed_kph=speed,
                    peak_deceleration_g=max(current_zone["peak_deceleration_g"], decel),
                    kinetic_loss_kjkg=current_zone["kinetic_loss_kjkg"] + kinetic,
                )
        else:
            if previous and previous.get("brake_on") is True and continuous:
                brake_release = t
            finish_zone()
        if brake_release is not None and throttle is not None and throttle >= 95:
            if 0 <= (t - brake_release) / 1000 <= 10:
                recoveries.append((t - brake_release) / 1000)
            brake_release = None
        full_seconds += weight * bool(throttle is not None and throttle >= 95)
        drs_seconds += weight * bool(row.get("drs_state") in (10, 12, 14))
        coast_seconds += weight * bool(
            speed >= 100
            and throttle is not None
            and throttle < 5
            and row.get("brake_on") is False
        )
        corner = min(1, (lateral or 0) / 4) ** 2 if green else 0.0
        traction = (
            clamp(max(0, accel or 0) / 1.5) * (throttle or 0) / 100 if green else 0.0
        )
        corner_sum += weight * corner
        traction_sum += weight * traction
        work = min(1, (wake or 0) / 100 * (lateral or 0) ** 2) if green else 0.0
        extra_work += weight * work
        wake_corner_integral += (
            weight * (wake / 100) * min(1, (lateral or 0) / 3) if green else 0
        )
        demand = clamp(0.65 * corner + 0.25 * traction + 2 * work)
        decay = math.exp(-weight / config.tyre_cooling_time_s)
        thermal = thermal * decay + demand * (1 - decay)
        if (
            continuous
            and green
            and plateau_step(previous["speed_kph"], speed, brake, throttle)
        ):
            if plateau_start is None:
                plateau_start = previous["session_time_ms"]
                plateau_n = 1
            plateau_n += 1
            if (
                t - plateau_start >= PLATEAU_DURATION_MS
                and plateau_n >= PLATEAU_SAMPLE_COUNT
                and not plateau_emitted
            ):
                events.append(
                    event(
                        "braking_anomaly",
                        entry.id,
                        plateau_start,
                        t,
                        "Braking anomaly",
                        "Brake is applied but sampled vehicle speed barely changes. Wheel lock is not observable from this feed.",
                        support=0.25,
                        evidence={"speed_kph": speed, "sample_count": plateau_n},
                        alternatives=[
                            "Pedal or speed sampling/rounding",
                            "Light brake application",
                            "Gradient or power/drag balance",
                            "A possible lock-up needs independent evidence",
                        ],
                    )
                )
                plateau_emitted = True
        else:
            plateau_start = None
            plateau_n = 0
            plateau_emitted = False
        if continuous and green and speed <= 5:
            if stop_start is None:
                stop_start = (
                    previous["session_time_ms"] if previous["speed_kph"] <= 5 else t
                )
                stop_samples = 1
            stop_samples += 1
            if t - stop_start >= 4000 and stop_samples >= 4 and not stop_emitted:
                events.append(
                    event(
                        "stopped_car",
                        entry.id,
                        stop_start,
                        t,
                        "Car stationary",
                        "Fresh observations show a sustained stop outside a known pit visit. Pit status may still be unreported.",
                        support=0.7,
                        severity="watch",
                        evidence={"observed_stop_s": (t - stop_start) / 1000},
                        alternatives=[
                            "Mechanical issue",
                            "Spin or collision",
                            "Unknown pit or recovery activity",
                        ],
                    )
                )
                stop_emitted = True
            if t - stop_start >= 4000 and not incident_emitted:
                approach = [
                    r
                    for r in rows
                    if stop_start - 5000 <= r["session_time_ms"] <= stop_start
                ]
                if (
                    approach
                    and max(r["speed_kph"] for r in approach) >= 150
                    and max(r["speed_kph"] for r in approach) - speed >= 80
                ):
                    events.append(
                        event(
                            "possible_incident",
                            entry.id,
                            stop_start,
                            t,
                            "Possible incident",
                            "A substantial speed loss is followed by a non-pit stop. The feed cannot establish a collision.",
                            support=0.5,
                            severity="warning",
                            evidence={
                                "approach_speed_kph": max(
                                    r["speed_kph"] for r in approach
                                ),
                                "observed_stop_s": (t - stop_start) / 1000,
                            },
                            alternatives=[
                                "Mechanical retirement",
                                "Spin without contact",
                                "Unreported pit/recovery stop",
                            ],
                        )
                    )
                    incident_emitted = True
        else:
            stop_start = None
            stop_samples = 0
            stop_emitted = incident_emitted = False
        if (
            continuous
            and green
            and previous
            and t > rpm_emitted_until
            and row.get("gear") == previous.get("gear")
            and finite(row.get("rpm"))
            and finite(previous.get("rpm"))
            and previous["rpm"] > 5000
            and throttle is not None
            and throttle > 70
            and row["rpm"] > previous["rpm"] * 1.12
            and speed - previous["speed_kph"] < 2
        ):
            events.append(
                event(
                    "traction_disruption",
                    entry.id,
                    previous["session_time_ms"],
                    t,
                    "Traction disruption candidate",
                    "Engine RPM rises in the same gear without a matching speed gain. Wheelspin is one possible explanation.",
                    support=0.3,
                    evidence={
                        "rpm_change": row["rpm"] - previous["rpm"],
                        "gear": row.get("gear"),
                    },
                    alternatives=[
                        "Clutch or gear transient",
                        "Unsynchronised samples",
                        "Speed/RPM measurement noise",
                    ],
                )
            )
            rpm_emitted_until = t + 5000
        if close:
            if pressure_started is None:
                pressure_started = t
            if t - pressure_started >= 5000 and not pressure_notified:
                events.append(
                    event(
                        "traffic_pressure",
                        entry.id,
                        pressure_started,
                        t,
                        "Sustained close following",
                        "A very short reported headway persists. Wake effects, tow and driver intent depend on the local situation.",
                        support=0.65,
                        severity="info",
                        evidence={"gap_s": gap},
                    )
                )
                pressure_notified = True
        else:
            pressure_started = None
            pressure_notified = False
        series.append(
            {
                "time_ms": t,
                "speed_kph": speed,
                "gap_s": gap,
                "wake_scenario_pct": wake if following else None,
                "tyre_load_index": thermal * 100 if lateral is not None else None,
                "lateral_g": lateral,
                "acceleration_g": accel,
                "green": green,
            }
        )
        last_lateral, last_wake, last_gap = lateral, wake, gap
        previous = row
    finish_zone()
    fresh = bool(
        rows
        and request.as_of_ms - rows[-1]["session_time_ms"]
        <= config.max_telemetry_gap_ms
    )
    support = clamp(seconds / max(1, (request.as_of_ms - start) / 1000))
    result.put("telemetry_coverage_pct", support * 100)
    result.put("observed_window_s", seconds)
    result.put(
        "latest_sample_age_s",
        (request.as_of_ms - rows[-1]["session_time_ms"]) / 1000 if rows else None,
    )
    result.put("gap_coverage_pct", 100 * gap_seconds / seconds if seconds else None)
    for key, value in (
        ("neutralised_time_pct", 100 * neutralised / seconds if seconds else None),
        ("close_following_s", close_seconds if gap_seconds else None),
        (
            "traffic_time_pct",
            100 * traffic_seconds / seconds if seconds and gap_seconds else None,
        ),
        (
            "wake_exposure_pct",
            100 * traffic_seconds / seconds if seconds and gap_seconds else None,
        ),
        ("lapped_traffic_s", lap_traffic),
        ("tow_exposure_s", tow_seconds),
        ("wake_corner_exposure_s", corner_traffic),
        ("brake_time_pct", 100 * brake_seconds / seconds if seconds else None),
        ("full_throttle_pct", 100 * full_seconds / seconds if seconds else None),
        ("drs_active_pct", 100 * drs_seconds / seconds if seconds else None),
        ("lift_coast_s", coast_seconds),
        ("braking_kinetic_loss_kjkg", energy),
        ("braking_zone_count", len(zones)),
        (
            "mean_braking_deceleration_g",
            decel_sum / decel_seconds if decel_seconds else None,
        ),
        ("peak_deceleration_g", peak_decel if decel_seconds else None),
        ("throttle_recovery_s", median(recoveries) if recoveries else None),
    ):
        result.put(key, value if seconds else None, support)
    result.put(
        "current_speed_kph",
        rows[-1]["speed_kph"] if fresh else None,
        support,
        reason=(
            None
            if fresh
            else "No recent speed sample for this driver at the replay clock."
        ),
        unavailable_cause="missing_data",
    )
    result.put(
        "current_throttle_pct",
        number(rows[-1].get("throttle_pct")) if fresh else None,
        support,
    )
    result.put("acceleration_g", last_accel if fresh else None, support)
    result.put("lateral_acceleration_g", last_lateral if fresh else None, support * 0.5)
    result.put(
        "current_stopped_s",
        (
            (rows[-1]["session_time_ms"] - stop_start) / 1000
            if fresh and stop_start is not None and stop_samples >= 4
            else 0 if fresh else None
        ),
        support,
    )
    for kind, key in (
        ("braking_anomaly", "braking_anomaly_count"),
        ("traction_disruption", "traction_disruption_count"),
        ("possible_incident", "abrupt_slowdown_count"),
    ):
        result.put(
            key, sum(e.kind == kind for e in events) if seconds else None, support
        )
    concern = (
        65
        if incident_emitted and stop_start is not None
        else 35 if stop_start is not None and stop_samples >= 4 else 0
    )
    result.put("incident_concern_index", concern if fresh else None, support * 0.5)
    for key, value in (
        ("corner_load_index", 100 * corner_sum / seconds if seconds else None),
        ("traction_load_index", 100 * traction_sum / seconds if seconds else None),
        ("wake_extra_work_index", 100 * extra_work / seconds if seconds else None),
    ):
        result.put(
            key,
            (
                value
                if key == "traction_load_index" or geometry_seconds >= seconds * 0.5
                else None
            ),
            support * 0.5,
        )
    result.put(
        "tyre_thermal_load_index",
        thermal * 100 if seconds and geometry_seconds >= seconds * 0.5 else None,
        support * 0.4,
        lower=0,
        upper=min(100, thermal * 170),
        reason="Requires geometry coverage. Window-start thermal state is assumed zero. This is workload exposure, not temperature or wear.",
    )
    wear = (
        100
        * clamp((0.5 * corner_sum + 0.3 * traction_sum + 0.2 * extra_work) / seconds)
        if seconds and geometry_seconds >= seconds * 0.5
        else None
    )
    result.put("wear_pressure_index", wear, support * 0.4)
    wake_load = (
        100 * wake_corner_integral / seconds
        if seconds and gap_seconds and geometry_seconds >= seconds * 0.5
        else None
    )
    result.put("wake_load_index", wake_load, support * 0.4)
    result.put(
        "mean_ahead_gap_s", gap_integral / gap_seconds if gap_seconds else None, support
    )
    result.put(
        "mean_headway_distance_m",
        distance_integral / gap_seconds if gap_seconds else None,
        support * 0.5,
    )
    gap = ahead.get("gap_s")
    # The last telemetry must also be fresh before attaching physical implications to a timing report.
    result.put(
        "ahead_gap_s",
        gap,
        0.7 if gap is not None else 0,
        reason=(
            None
            if gap is not None
            else "No fresh interval identifies a car ahead. Check the timing position and traffic at this point."
        ),
        unavailable_cause="missing_data",
    )
    distance = gap * rows[-1]["speed_kph"] / 3.6 if gap is not None and fresh else None
    result.put(
        "ahead_distance_scenario_m",
        distance,
        support * 0.5,
        lower=max(0, distance * 0.7) if distance is not None else None,
        upper=distance * 1.3 if distance is not None else None,
    )
    phase = phase_at(data.track_status, request.as_of_ms)
    wake_reason = wake_cause = None
    if session_end is not None and request.as_of_ms >= session_end:
        wake_cause, wake_reason = (
            "outside_window",
            "The race has finished. Seek to a green-flag lap before the finish.",
        )
    elif race_start is None or request.as_of_ms < race_start:
        wake_cause, wake_reason = (
            "outside_window",
            "This driver has no lap start at this time. Seek into the race.",
        )
    elif phase == "unknown":
        wake_cause, wake_reason = (
            "missing_data",
            "Track status has not been reported at this time.",
        )
    elif phase != "1" or in_pit(entry, request.as_of_ms, context):
        wake_cause, wake_reason = (
            "not_applicable",
            "This scenario applies to green-flag running outside the pits.",
        )
    elif not fresh:
        wake_cause, wake_reason = (
            "missing_data",
            "No recent car telemetry for this driver. The car may have stopped reporting.",
        )
    end_green = wake_reason is None
    if end_green:
        if gap is None:
            wake_cause, wake_reason = (
                "missing_data",
                "A fresh timed gap to the car ahead is required.",
            )
        elif gap > config.traffic_gap_s or rows[-1]["speed_kph"] < 40:
            wake_cause, wake_reason = (
                "not_applicable",
                f"Requires at least 40 km/h and a gap of {config.traffic_gap_s:g} s or less.",
            )
    loss = (
        wake_loss(distance, config)
        if distance is not None and wake_reason is None
        else None
    )
    result.put(
        "wake_loss_scenario_pct",
        loss,
        support * 0.4,
        lower=0,
        upper=min(60, loss * 1.7) if loss is not None else None,
        reason=wake_reason
        or "Design-prior scenario. Lateral overlap and car-specific aero coefficients are unknown.",
        unavailable_cause=wake_cause,
    )
    put_weather(
        conditions,
        request,
        rows[-1] if fresh else None,
        (
            heading
            if positions.get(request.as_of_ms, config.max_telemetry_gap_ms)
            else None
        ),
        result,
    )
    rho = conditions.get("air_density_kgm3")
    airspeed = result.metrics["relative_air_speed_kph"].value
    central_speed = (
        airspeed
        if isinstance(airspeed, (int, float))
        else rows[-1]["speed_kph"] if fresh else None
    )
    ratio = (
        config.downforce_weight_ratio_at_200kph
        * (central_speed / 200) ** 2
        * ((rho or 1.225) / 1.225)
        if fresh
        else None
    )
    result.put(
        "aero_load_ratio",
        ratio,
        support * 0.35,
        lower=ratio * 0.6 if ratio is not None else None,
        upper=ratio * 1.6 if ratio is not None else None,
    )
    corner_loss = (
        100 * (1 - math.sqrt((1 + ratio * (1 - loss / 100)) / (1 + ratio)))
        if loss is not None and ratio is not None
        else None
    )
    result.put(
        "corner_speed_loss_scenario_pct",
        corner_loss,
        support * 0.3,
        lower=0,
        upper=corner_loss * 1.8 if corner_loss is not None else None,
        reason=wake_reason,
        unavailable_cause=wake_cause,
    )
    tow = (
        loss * 0.35
        if loss is not None and last_lateral is not None and last_lateral < 0.25
        else None
    )
    result.put(
        "tow_drag_relief_scenario_pct",
        tow,
        support * 0.25,
        lower=0,
        upper=tow * 2 if tow is not None else None,
    )
    closing, trend_support = traffic.recent_trend(entry.car_number, request.as_of_ms)
    result.put("gap_closing_rate", closing, trend_support)
    projection = (
        max(0, gap - closing * request.prediction_horizon_s)
        if gap is not None and closing is not None
        else None
    )
    result.put(
        "projected_gap_s",
        projection,
        trend_support * 0.7,
        lower=max(0, projection - 0.5) if projection is not None else None,
        upper=projection + 0.5 if projection is not None else None,
    )
    result.put(
        "catch_time_s",
        (
            gap / closing
            if gap is not None
            and closing is not None
            and closing > 0
            and gap / closing <= 120
            else None
        ),
        trend_support * 0.5,
    )
    attack = (
        100 * clamp(1 - gap / 2) * (0.35 + 0.65 * clamp((closing or 0) / 0.05))
        if gap is not None and end_green
        else None
    )
    result.put("attack_opportunity_index", attack, support * 0.4)
    put_pace(entry, data, request, traffic, result)
    put_brake_shift(entry, data, request, zones, rows, result)
    step = max(1, math.ceil(len(series) / 240))
    output_series = series[::step]
    if series and output_series[-1] is not series[-1]:
        output_series.append(series[-1])
    return (
        DriverEstimate(
            entry_id=entry.id,
            car_number=entry.car_number,
            ahead_entry_id=ahead.get("ahead_id"),
            metrics=result.metrics,
            series=output_series,
            braking_zones=zones[-40:],
            pace_laps=[
                {
                    "lap": lap["lap_number"],
                    "time_s": lap["lap_time_ms"] / 1000,
                    "tyre_age": lap.get("tyre_life"),
                    "stint_number": lap.get("stint_number"),
                    "compound": lap.get("compound"),
                }
                for lap in entry.laps
                if is_clean(lap)
            ][-12:],
        ),
        events,
    )


def put_pace(entry, data, request, traffic, result):
    laps = [
        lap
        for lap in entry.laps
        if is_clean(lap)
        and lap.get("lap_end_time_ms") is not None
        and lap["lap_end_time_ms"] <= request.as_of_ms
    ]
    laps.sort(key=lambda lap: lap["lap_number"])
    if not laps:
        return
    compound = laps[-1].get("compound")
    stint = laps[-1].get("stint_number")
    comparable = [
        lap
        for lap in laps
        if lap.get("compound") == compound and lap.get("stint_number") == stint
    ][-8:]
    values = [lap["lap_time_ms"] / 1000 for lap in comparable]
    pace = median(values[-5:])
    result.put("recent_pace_s", pace, min(1, len(values) / 5))
    result.put("tyre_age_laps", number(laps[-1].get("tyre_life")), 0.85)
    result.put("pace_sample_laps", len(values))
    result.put(
        "last_lap_delta_s",
        values[-1] - median(values[:-1]) if len(values) > 1 else None,
        min(1, len(values) / 5),
    )
    result.put(
        "pace_consistency_pct",
        (
            100 * median(abs(v - pace) for v in values) / pace
            if pace > 0 and len(values) >= 3
            else None
        ),
        min(1, len(values) / 5),
    )
    trend = (
        robust_slope(
            [(lap["lap_number"], lap["lap_time_ms"] / 1000) for lap in comparable]
        )
        if len(comparable) >= 4
        else None
    )
    result.put(
        "stint_pace_slope",
        trend,
        0.5,
        reason="Fuel, tyre condition, track evolution and weather are not separated by this raw trend.",
    )
    result.put(
        "laps_to_pace_limit_scenario",
        min(100, 1 / trend) if trend is not None and trend > 0.02 else None,
        0.25,
        reason="Constant pace-trend scenario, not remaining tyre life.",
    )
    groups = {"clear": [], "traffic": []}
    reports = traffic.intervals.get(entry.car_number, [])
    for lap in comparable:
        begin, end = lap.get("lap_start_time_ms"), lap.get("lap_end_time_ms")
        if begin is None or end is None:
            continue
        observations = [
            number(row.get("interval"))
            for row in reports
            if begin
            <= row["session_time_ms"]
            <= end - request.assumptions.source_report_delay_ms
        ]
        observations = [v for v in observations if v is not None and v > 0]
        # Four-second source cadence: do not classify a lap from one isolated report.
        if len(observations) < max(3, (end - begin) / 1000 / 8):
            continue
        exposure = sum(
            v <= request.assumptions.traffic_gap_s for v in observations
        ) / len(observations)
        if exposure <= 0.1:
            groups["clear"].append(lap["lap_time_ms"] / 1000)
        if exposure >= 0.5:
            groups["traffic"].append(lap["lap_time_ms"] / 1000)
    reference = median(groups["clear"]) if len(groups["clear"]) >= 2 else None
    result.put("clean_air_reference_s", reference, 0.55)
    loss = (
        median(groups["traffic"]) - reference
        if len(groups["traffic"]) >= 2 and reference is not None
        else None
    )
    result.put(
        "traffic_correlated_loss_s",
        loss,
        0.4,
        reason="Same-compound association. It does not establish dirty air as the cause of the difference.",
    )
