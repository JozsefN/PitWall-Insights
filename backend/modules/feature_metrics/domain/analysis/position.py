import numpy as np
from .common import stat, weighted_mean, episodes, numeric, weights
from .geometry import position_arrays


def calculate_position(data, request, result):
    for entry in data.entries:
        if not entry.positions:
            result.missing(
                "position",
                entry.id,
                "Position telemetry is not materialized for this selection.",
            )
            continue
        times, xy, usable, duration, dt, delta, distance, speed, valid, jumps = (
            position_arrays(entry, data, request)
        )
        n = int(np.sum(usable))
        support = min(
            0.85,
            float(np.sum(duration[usable]))
            / max(1, (data.end_ms - data.start_ms) / 1000),
        )

        def put(key, value, confidence=None, warnings=()):
            result.put(
                key,
                value,
                entry.id,
                n=n,
                confidence=support if confidence is None else min(support, confidence),
                warnings=warnings,
            )

        put(
            "position_distance_m",
            float(np.sum(distance[valid])) if np.any(valid) else None,
        )
        put("mean_position_speed_kph", weighted_mean(speed, np.where(valid, dt, 0)))
        put("max_position_speed_kph", stat(speed, "max"))
        headings = np.arctan2(delta[:, 1], delta[:, 0])
        turns = (np.diff(headings) + np.pi) % (2 * np.pi) - np.pi
        elapsed = (dt[:-1] + dt[1:]) / 2
        turning = (
            valid[:-1]
            & valid[1:]
            & (distance[:-1] > 0.5)
            & (distance[1:] > 0.5)
            & (elapsed > 0)
        )
        rate = np.full(len(turns), np.nan)
        rate[turning] = np.abs(turns[turning]) / elapsed[turning]
        lateral = rate * (speed[:-1] + speed[1:]) / 2 / 3.6 / 9.80665
        lateral[(lateral > 10) | ~turning] = np.nan
        put("max_heading_rate_deg_s", stat(np.rad2deg(rate), "max"), 0.6)
        put(
            "max_estimated_lateral_g",
            stat(lateral, "max"),
            0.4,
            ["Path-derived estimate; quantization and display sampling affect peaks."],
        )
        flags = (
            np.array(
                [
                    str(row.get("track_status", "")).lower() == "offtrack"
                    for row in entry.positions
                ]
            )
            & usable
        )
        flag_known = (
            np.array([row.get("track_status") is not None for row in entry.positions])
            & usable
        )
        put(
            "reported_offtrack_time_s",
            float(np.sum(duration[flags])) if np.any(flag_known) else None,
            0.5,
            [
                "The source flag can indicate unavailable position data; it is not an official track-limits verdict."
            ],
        )
        runs = episodes(flags, times, duration)
        put(
            "reported_offtrack_episode_count",
            len(runs) if np.any(flag_known) else None,
            0.5,
        )
        for start, end, length in runs:
            result.event(
                "reported_offtrack",
                entry.id,
                times[start],
                times[end - 1] + duration[end - 1] * 1000,
                0.5,
                "reported",
                duration_s=length,
            )
        if data.reference is None:
            for key in (
                "mean_line_deviation_m",
                "p95_line_deviation_m",
                "max_line_deviation_m",
                "large_line_deviation_time_s",
                "reference_lap_length_m",
            ):
                put(
                    key,
                    None,
                    warnings=["A complete, usable reference lap is unavailable."],
                )
        else:
            deviations = np.full(len(times), np.nan)
            deviations[usable], _ = data.reference.project(xy[usable])
            # Exclude positions adjacent to an impossible teleport from geometry claims.
            near_jump = np.r_[jumps, False] | np.r_[False, jumps]
            deviations[near_jump] = np.nan
            for key, operation in (
                ("mean_line_deviation_m", "mean"),
                ("p95_line_deviation_m", "p95"),
                ("max_line_deviation_m", "max"),
            ):
                put(
                    key,
                    stat(deviations, operation),
                    0.6,
                    [
                        "Reference racing-line distance; track boundaries are not available."
                    ],
                )
            put(
                "large_line_deviation_time_s",
                float(np.sum(duration[deviations > request.options.line_deviation_m])),
                0.5,
            )
            put("reference_lap_length_m", data.reference.length, 0.8)
            for start, end, length in episodes(
                deviations > request.options.line_deviation_m, times, duration
            ):
                if length >= 1:
                    result.event(
                        "line_deviation",
                        entry.id,
                        times[start],
                        times[end - 1] + duration[end - 1] * 1000,
                        0.45,
                        "candidate",
                        max_distance_m=stat(deviations[start:end], "max"),
                        duration_s=length,
                        track_boundary_known=False,
                    )


def calculate_quality(data, request, result):
    for entry in data.entries:

        def put(key, value, n):
            result.put(key, value, entry.id, n=n)

        put("car_sample_count", len(entry.car), len(entry.car))
        put("position_sample_count", len(entry.positions), len(entry.positions))
        for name, rows in (("car", entry.car), ("position", entry.positions)):
            times = numeric(rows, "session_time_ms")
            gaps = np.diff(times)
            duration = weights(
                times, data.start_ms, data.end_ms, request.options.max_sample_gap_ms
            )
            if name == "position":
                _, _, usable, *_ = position_arrays(entry, data, request)
                duration = duration * usable
            put(
                name + "_time_coverage_pct",
                (
                    min(
                        100,
                        float(np.sum(duration))
                        / max(1, (data.end_ms - data.start_ms) / 1000)
                        * 100,
                    )
                    if len(rows)
                    else None
                ),
                len(rows),
            )
            put(
                name + "_gap_count",
                (
                    int(np.sum(gaps > request.options.max_sample_gap_ms))
                    if len(rows)
                    else None
                ),
                len(rows),
            )
            put("largest_" + name + "_gap_ms", stat(gaps, "max"), len(rows))
            put(
                "median_" + name + "_interval_ms",
                stat(gaps[gaps > 0], "median"),
                len(rows),
            )
        speeds = numeric(entry.car, "speed_kph")
        put(
            "invalid_speed_sample_count",
            (
                int(
                    np.sum(
                        ~np.isfinite(speeds)
                        | (speeds < 0)
                        | (speeds > request.options.max_plausible_speed_kph)
                    )
                )
                if len(speeds)
                else None
            ),
            len(speeds),
        )
        _, _, usable, _, _, _, distance, _, valid, jumps = position_arrays(
            entry, data, request
        )
        put(
            "invalid_position_sample_count",
            int(np.sum(~usable)) if len(usable) else None,
            len(usable),
        )
        put(
            "position_jump_count",
            int(np.sum(jumps)) if len(usable) else None,
            len(usable),
        )
        put(
            "repeated_position_pct",
            (
                float(np.sum((distance == 0) & valid)) / np.sum(valid) * 100
                if np.any(valid)
                else None
            ),
            len(usable),
        )
