"""Comparable timing over equal-distance bins on a shared reference lap."""

from statistics import median

import numpy as np

from ..analysis.geometry import ReferenceLine
from ..race_estimation.common import finite


def reference_for_selected_lap(lap, positions):
    start, end = lap.get("lap_start_time_ms"), lap.get("lap_end_time_ms")
    if start is None or end is None:
        return None
    rows = [
        row
        for row in positions
        if start <= row["session_time_ms"] <= end
        and finite(row.get("x"))
        and finite(row.get("y"))
    ]
    times = [row["session_time_ms"] for row in rows]
    if (
        len(times) < 20
        or times[0] - start > 1200
        or end - times[-1] > 1200
        or max(np.diff(times)) > 2000
    ):
        return None
    try:
        return ReferenceLine(
            np.array([[row["x"], row["y"]] for row in rows]) * 0.1,
            lap_id=lap.get("id"),
            sample_times_ms=np.asarray(times) - start,
            lap_duration_ms=end - start,
        )
    except ValueError:
        return None


def lap_segments(reference, lap, positions, car, count):
    start, end = lap.get("lap_start_time_ms"), lap.get("lap_end_time_ms")
    if reference is None or start is None or end is None or end <= start:
        return []
    rows = [
        row
        for row in positions
        if start <= row["session_time_ms"] <= end
        and finite(row.get("x"))
        and finite(row.get("y"))
    ]
    if len(rows) < max(20, count * 2):
        return []
    times = np.array([row["session_time_ms"] for row in rows], dtype=float)
    if (
        times[0] - start > 1200
        or end - times[-1] > 1200
        or np.max(np.diff(times)) > 2000
    ):
        return []
    error, pct = reference.project(
        np.array([[row["x"], row["y"]] for row in rows], dtype=float) * 0.1
    )
    unwrapped = np.unwrap(pct * 2 * np.pi / 100) * 100 / (2 * np.pi)
    unwrapped -= round(unwrapped[0] / 100) * 100
    if (
        np.max(error) > 40
        or abs(unwrapped[0]) > 2
        or abs(unwrapped[-1] - 100) > 2
        or np.min(np.diff(unwrapped)) < -2
        or np.max(np.diff(unwrapped)) > 8
    ):
        return []
    progress = np.clip(np.maximum.accumulate(unwrapped), 0, 100)
    bins = np.linspace(0, 100, count + 1)
    # Do not silently extrapolate any internal segment crossing.
    if progress[0] > bins[1] or progress[-1] < bins[-2]:
        return []
    first_indices = np.unique(progress, return_index=True)[1]
    stamps = np.interp(bins, progress[first_indices], times[first_indices])
    stamps[0], stamps[-1] = start, end
    output = []
    for index, (left, right) in enumerate(zip(stamps, stamps[1:])):
        if right <= left:
            return []
        controls = [row for row in car if left <= row["session_time_ms"] < right]
        speed = [
            row["speed_kph"]
            for row in controls
            if finite(row.get("speed_kph")) and 0 <= row["speed_kph"] <= 450
        ]
        throttle = [
            row["throttle_pct"]
            for row in controls
            if finite(row.get("throttle_pct")) and 0 <= row["throttle_pct"] <= 100
        ]
        brake = [
            row["brake_on"] for row in controls if isinstance(row.get("brake_on"), bool)
        ]
        output.append(
            {
                "segment": index + 1,
                "start_pct": float(bins[index]),
                "end_pct": float(bins[index + 1]),
                "start_ms": round(left),
                "end_ms": round(right),
                "time_s": round((right - left) / 1000, 3),
                "min_speed_kph": min(speed) if speed else None,
                "max_speed_kph": max(speed) if speed else None,
                "mean_throttle_pct": (
                    sum(throttle) / len(throttle) if throttle else None
                ),
                "brake_sample_pct": 100 * sum(brake) / len(brake) if brake else None,
                "car_samples": len(controls),
            }
        )
    return output


def compare_segments(rows):
    by_segment = {}
    for lap in rows:
        for segment in lap["segments"]:
            by_segment.setdefault(segment["segment"], []).append((lap, segment))
    for candidates in by_segment.values():
        fastest = min(segment["time_s"] for _, segment in candidates)
        for lap, segment in candidates:
            previous = [
                other["time_s"]
                for other_lap, other in candidates
                if other_lap["entry_id"] == lap["entry_id"]
                and other_lap["lap_number"] < lap["lap_number"]
            ]
            own = min(previous) if previous else None
            # Allow a tolerance consistent with the approximate source clocks.
            segment["delta_to_best_s"] = (
                round(segment["time_s"] - fastest, 3) if len(candidates) >= 2 else None
            )
            segment["delta_to_prior_median_s"] = (
                round(segment["time_s"] - median(previous), 3) if previous else None
            )
            segment["colour"] = (
                "purple"
                if len({item[0]["entry_id"] for item in candidates}) >= 2
                and segment["time_s"] <= fastest + 0.02
                else (
                    "green"
                    if own is not None and segment["time_s"] < own - 0.02
                    else "yellow" if own is not None else "unknown"
                )
            )
