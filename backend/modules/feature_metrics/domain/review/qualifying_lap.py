"""Session-wide qualifying splits on one physical lap reference."""

import numpy as np

from .segments import lap_segments, reference_for_selected_lap

MINISECTORS = 20
SECTOR_KEYS = tuple(f"sector_{i}_time_ms" for i in (1, 2, 3))


def eligible_lap(lap):
    return (
        (lap.get("lap_time_ms") or 0) > 0
        and not lap.get("is_deleted")
        and not lap.get("is_generated")
        and lap.get("pit_in_time_ms") is None
        and lap.get("pit_out_time_ms") is None
    )


def qualifying_splits(laps, focus, positions, *, include_minisectors):
    reference, reference_lap = None, None
    for lap in sorted(laps, key=lambda row: (row["lap_time_ms"], row["id"])):
        reference = reference_for_selected_lap(lap, positions.get(lap["id"], []))
        if reference is not None:
            reference_lap = lap
            break

    official = {
        lap["id"]: [lap.get(key) for key in SECTOR_KEYS] for lap in laps
    }
    geometry = _geometry(reference) if reference else []
    official_bounds = _official_bounds(reference, reference_lap) if reference else []
    mini_bounds = list(np.linspace(0, 100, MINISECTORS + 1)) if reference else []
    mini = {}
    if include_minisectors and reference:
        for lap in laps:
            samples = positions.get(lap["id"])
            if samples:
                segments = lap_segments(reference, lap, samples, [], MINISECTORS)
                if segments:
                    mini[lap["id"]] = [item["end_ms"] - item["start_ms"] for item in segments]

    return {
        "outline": [point for _, point in geometry],
        "sectors": _rank(laps, focus, official, 3, official_bounds, geometry),
        "minisectors": _rank(laps, focus, mini, MINISECTORS, mini_bounds, geometry)
        if include_minisectors else [],
        "minisector_driver_count": len({lap["session_entry_id"] for lap in laps if lap["id"] in mini}),
        "minisector_lap_count": len(mini),
        "focus_minisectors_available": focus["id"] in mini,
    }


def _geometry(reference):
    return [
        (float(pct), [round(float(x) * 10, 1), round(float(y) * 10, 1)])
        for pct, (x, y) in zip(
            np.r_[reference.arcs / reference.length * 100, 100],
            np.vstack((reference.points, reference.points[0])),
        )
    ]


def _official_bounds(reference, lap):
    s1, s2, _ = (lap.get(key) for key in SECTOR_KEYS)
    if not s1 or not s2 or reference.sample_times_ms is None:
        return []
    bounds = np.interp(
        [s1, s1 + s2], reference.sample_times_ms, reference.arcs / reference.length * 100,
    )
    if not 0 < bounds[0] < bounds[1] < 100:
        return []
    return [0, *bounds, 100]


def _path(geometry, start, end):
    progress, points = zip(*geometry)
    x, y = zip(*points)

    def edge(at):
        return [round(float(np.interp(at, progress, axis)), 1) for axis in (x, y)]

    return [edge(start), *(point for pct, point in geometry if start < pct < end), edge(end)]


def _rank(laps, focus, times, count, bounds, geometry):
    best = [{} for _ in range(count)]
    for lap in laps:
        for i, time in enumerate(times.get(lap["id"], [])):
            if time is None or time <= 0:
                continue
            entry = lap["session_entry_id"]
            previous = best[i].get(entry)
            candidate = (time, lap["lap_number"])
            if previous is None or candidate < previous:
                best[i][entry] = candidate

    selected = times.get(focus["id"], [None] * count)
    results = []
    for i, drivers in enumerate(best):
        ordered = sorted(drivers.items(), key=lambda item: (item[1][0], item[0]))
        focus_ms = selected[i] if (selected[i] or 0) > 0 else None
        best_ms = ordered[0][1][0] if ordered else None
        own = drivers.get(focus["session_entry_id"])
        colour = "unknown"
        if focus_ms is not None and own:
            if focus_ms == best_ms and len(ordered) >= 2:
                colour = "purple"
            else:
                colour = "green" if focus_ms == own[0] else "yellow"
        results.append({
            "number": i + 1,
            "focus_ms": focus_ms,
            "focus_delta_ms": focus_ms - best_ms if focus_ms is not None and best_ms is not None else None,
            "colour": colour,
            "path": _path(geometry, bounds[i], bounds[i + 1]) if bounds else [],
            "ranking": [
                {"entry_id": entry, "lap_number": lap, "time_ms": time,
                 "delta_ms": time - best_ms, "delta_to_focus_ms": time - focus_ms if focus_ms is not None else None}
                for entry, (time, lap) in ordered
            ],
        })
    return results
