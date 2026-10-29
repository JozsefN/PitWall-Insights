import re
import numpy as np
from .common import numeric, weights, weighted_mean, stat


def calculate_conditions(data, request, result):
    times = numeric(data.weather, "session_time_ms")
    duration = weights(times, data.start_ms, data.end_ms, 180000)
    active = duration > 0

    def put(key, value, n=None):
        result.put(key, value, n=len(data.weather) if n is None else n)

    for key, column, operation in (
        ("mean_air_temp_c", "air_temp_c", "weighted"),
        ("mean_track_temp_c", "track_temp_c", "weighted"),
        ("min_track_temp_c", "track_temp_c", "min"),
        ("max_track_temp_c", "track_temp_c", "max"),
        ("mean_humidity_pct", "humidity_pct", "weighted"),
        ("mean_pressure_mbar", "pressure_mbar", "weighted"),
        ("mean_wind_speed_kph", "wind_speed_kph", "weighted"),
        ("max_wind_speed_kph", "wind_speed_kph", "max"),
    ):
        values = numeric(data.weather, column)
        put(
            key,
            (
                weighted_mean(values, duration)
                if operation == "weighted"
                else stat(values[active], operation)
            ),
        )
    angles = np.deg2rad(numeric(data.weather, "wind_direction_deg"))
    sine, cosine = weighted_mean(np.sin(angles), duration), weighted_mean(
        np.cos(angles), duration
    )
    angle = (
        None
        if sine is None or np.hypot(sine, cosine) < 1e-6
        else float(np.rad2deg(np.arctan2(sine, cosine)) % 360)
    )
    if angle is not None and angle > 359.999999:
        angle = 0.0
    put("mean_wind_direction_deg", angle)
    rain = numeric(data.weather, "rainfall")
    put(
        "reported_rain_time_s",
        (
            float(np.sum(duration[rain == 1]))
            if np.any(np.isfinite(rain) & active)
            else None
        ),
    )
    statuses = sorted(data.track_status, key=lambda row: row["session_time_ms"])
    elapsed = {code: 0.0 for code in ("1", "2", "4", "5", "6", "7")}
    known = False
    for index, row in enumerate(statuses):
        end = (
            statuses[index + 1]["session_time_ms"]
            if index + 1 < len(statuses)
            else data.end_ms
        )
        span = (
            max(0, min(data.end_ms, end) - max(data.start_ms, row["session_time_ms"]))
            / 1000
        )
        code = str(row.get("status"))
        if code in elapsed and span > 0:
            elapsed[code] += span
            known = True
    for key, codes in (
        ("clear_track_time_s", ("1",)),
        ("yellow_track_time_s", ("2",)),
        ("safety_car_time_s", ("4",)),
        ("red_flag_time_s", ("5",)),
        ("vsc_time_s", ("6", "7")),
    ):
        put(key, sum(elapsed[code] for code in codes) if known else None, len(statuses))
    messages = [
        row
        for row in data.race_control
        if data.start_ms <= row["session_time_ms"] <= data.end_ms
    ]
    put("race_control_message_count", len(messages), len(messages))
    put(
        "lap_time_deleted_message_count",
        sum(
            bool(
                re.search(
                    r"lap time.*deleted|deleted.*lap time", row.get("message", ""), re.I
                )
            )
            for row in messages
        ),
        len(messages),
    )
