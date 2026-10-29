import numpy as np
from .common import selected_laps, stat, aligned_values, numeric
from .geometry import aligned_xy, position_arrays


def calculate_racing(data, request, result):
    field_best = {}
    for entry in data.entries:
        for lap in selected_laps(entry, data, request, clean=True):
            number = lap["lap_number"]
            field_best[number] = min(
                field_best.get(number, float("inf")), lap["lap_time_ms"]
            )
    # Shared clock and bounded interpolation prevent comparing different instants.
    step = max(1000, request.sample_interval_ms)
    clock = np.arange(data.start_ms, data.end_ms, step, dtype=float)
    closest = {entry.id: [] for entry in data.entries}
    close_time = {entry.id: 0.0 for entry in data.entries}
    observed = {entry.id: 0 for entry in data.entries}
    if len(data.entries) > 1:
        for offset in range(0, len(clock), 512):
            chunk = clock[offset : offset + 513]
            count = min(512, len(clock) - offset)
            coordinates = np.stack(
                [aligned_xy(entry, chunk, request) for entry in data.entries], axis=1
            )
            delta = coordinates[:, :, None, :] - coordinates[:, None, :, :]
            distance = np.sqrt(np.sum(delta**2, axis=3))
            distance[~np.isfinite(distance)] = np.inf
            distance[:, np.arange(len(data.entries)), np.arange(len(data.entries))] = (
                np.inf
            )
            nearest = np.min(distance, axis=2)
            for index, entry in enumerate(data.entries):
                valid = np.isfinite(nearest[:count, index])
                closest[entry.id].extend(nearest[:count, index][valid].tolist())
                observed[entry.id] += int(np.sum(valid))
                next_valid = np.r_[np.isfinite(nearest[1:, index]), False][:count]
                spans = np.minimum(step, data.end_ms - chunk[:count]) / 1000
                close_time[entry.id] += float(
                    np.sum(spans[valid & next_valid & (nearest[:count, index] < 30)])
                )
    for entry in data.entries:
        laps = selected_laps(entry, data, request)
        positions = [
            lap["lap_position"] for lap in laps if (lap.get("lap_position") or 0) > 0
        ]
        changes = np.diff(positions)

        def put(key, value, n=None, warnings=()):
            result.put(
                key,
                value,
                entry.id,
                n=len(laps) if n is None else n,
                confidence=0.8,
                warnings=warnings,
            )

        last = positions[-1] if positions else None
        put("last_reported_position", last)
        put(
            "positions_gained_from_grid",
            (
                entry.grid_position - last
                if last and (entry.grid_position or 0) > 0
                else None
            ),
        )
        put(
            "timing_position_gain_count",
            int(np.sum(-changes[changes < 0])) if positions else None,
        )
        put(
            "timing_position_loss_count",
            int(np.sum(changes[changes > 0])) if positions else None,
        )
        gaps = [
            lap["lap_time_ms"] - field_best[lap["lap_number"]]
            for lap in selected_laps(entry, data, request, clean=True)
        ]
        put(
            "median_lap_gap_to_field_best_ms",
            stat(gaps, "median"),
            len(gaps),
            [
                "Comparison field is the selected entries, without fuel/traffic corrections."
            ],
        )
        times, _, _, _, dt, _, _, speed, valid, _ = position_arrays(
            entry, data, request
        )
        reported = aligned_values(
            entry.car,
            "speed_kph",
            (times[:-1] + times[1:]) / 2,
            request.options.max_sample_gap_ms,
        )
        reported[
            (reported < 0) | (reported > request.options.max_plausible_speed_kph)
        ] = np.nan
        differences = np.abs(speed - reported)
        differences[~valid] = np.nan
        put(
            "mean_speed_delta_to_position_kph",
            stat(differences, "mean"),
            int(np.sum(np.isfinite(differences))),
        )
        put(
            "nearest_car_distance_m", stat(closest[entry.id], "min"), observed[entry.id]
        )
        put(
            "close_car_time_s",
            close_time[entry.id] if observed[entry.id] else None,
            observed[entry.id],
            [
                "Euclidean proximity includes pit lane and adjacent track sections; it does not establish following or contact."
            ],
        )
