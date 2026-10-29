from types import SimpleNamespace
import numpy as np
from modules.feature_metrics.domain.analysis.geometry import aligned_xy
from modules.feature_metrics.domain.analysis.models import AnalysisOptions
from .common import clean_laps, slope, mad, band, clear_interval


def crossings(entry, cutoff):
    output = {}
    for row in entry.laps:
        if row.get("is_generated"):
            continue
        number = row["lap_number"]
        for sector in range(1, 4):
            stamp = row.get(f"sector_{sector}_session_time_ms")
            if stamp is not None and stamp <= cutoff:
                output[(number, sector)] = stamp
        stamp = row.get("lap_end_time_ms")
        if stamp is not None and stamp <= cutoff:
            output[(number, 3)] = stamp
    return output


def pit_changed(entry, start, end):
    return any(
        start < row.get(key, -1) <= end
        for row in entry.laps
        for key in ("pit_in_time_ms", "pit_out_time_ms")
        if row.get(key) is not None
    )


def lap_numbers(entry, clock):
    rows = sorted(
        (row for row in entry.laps if row.get("lap_start_time_ms") is not None),
        key=lambda row: row["lap_start_time_ms"],
    )
    if not rows:
        return np.full(len(clock), np.nan)
    starts = np.array([row["lap_start_time_ms"] for row in rows])
    numbers = np.array([row["lap_number"] for row in rows], dtype=float)
    index = np.searchsorted(starts, clock, side="right") - 1
    output = numbers[np.clip(index, 0, len(rows) - 1)]
    output[index < 0] = np.nan
    return output


def pit_mask(entry, clock):
    last_in = np.full(len(clock), -1.0)
    last_out = np.full(len(clock), -1.0)
    for row in entry.laps:
        for name, output in (
            ("pit_in_time_ms", last_in),
            ("pit_out_time_ms", last_out),
        ):
            stamp = row.get(name)
            if stamp is not None:
                output[clock >= stamp] = np.maximum(output[clock >= stamp], stamp)
    return last_in > last_out


def rival_features(data, request, result):
    focus = next(entry for entry in data.entries if entry.id == request.focus_entry_id)
    rivals = [
        entry
        for entry in data.entries
        if entry.id != focus.id
        and (request.rival_entry_ids is None or entry.id in request.rival_entry_ids)
    ]
    target_cross = crossings(focus, request.as_of_ms)
    own_clean = {lap["lap_number"]: lap for lap in clean_laps(focus, request.as_of_ms)}
    pace = result.get("strategy_recent_pace_s", focus.id)
    clock = np.arange(
        max(data.start_ms, request.as_of_ms - request.telemetry_lookback_ms),
        request.as_of_ms + 1,
        1000,
        dtype=float,
    )
    config = SimpleNamespace(
        options=AnalysisOptions(
            max_sample_gap_ms=max(2000, 2 * request.sample_interval_ms)
        )
    )
    coordinates = {
        entry.id: aligned_xy(entry, clock, config) for entry in [focus, *rivals]
    }
    progress = {}
    if data.reference is not None:
        for entry in [focus, *rivals]:
            xy = coordinates[entry.id]
            valid = np.all(np.isfinite(xy), axis=1) & ~pit_mask(entry, clock)
            arc = np.full(len(clock), np.nan)
            if np.any(valid):
                error, along = data.reference.project(xy[valid])
                observed = (
                    lap_numbers(entry, clock)[valid] - 1 + along / 100
                ) * data.reference.length
                observed[error > 15] = np.nan
                arc[valid] = observed
            # Reject discontinuities introduced by ambiguous projection/start-line alignment.
            delta = np.diff(arc)
            jumps = np.isfinite(delta) & ((delta < -5) | (delta > 450 / 3.6 + 5))
            arc[np.flatnonzero(jumps) + 1] = np.nan
            progress[entry.id] = arc
    series = {}
    pair_state = {}
    for rival in rivals:
        other_cross = crossings(rival, request.as_of_ms)
        shared = sorted(target_cross.keys() & other_cross.keys())[-60:]
        points = [
            dict(
                lap=number,
                sector=sector,
                time_ms=max(
                    target_cross[(number, sector)], other_cross[(number, sector)]
                ),
                gap_s=(target_cross[(number, sector)] - other_cross[(number, sector)])
                / 1000,
            )
            for number, sector in shared
        ]
        points.sort(key=lambda row: row["time_ms"])
        series[rival.id] = points
        last = points[-1] if points else None
        other_clean = {
            lap["lap_number"]: lap for lap in clean_laps(rival, request.as_of_ms)
        }
        common = sorted(own_clean.keys() & other_clean.keys())[-10:]
        lap_gaps = [
            (
                own_clean[number]["lap_end_time_ms"]
                - other_clean[number]["lap_end_time_ms"]
            )
            / 1000
            for number in common
        ]
        times = [
            max(
                own_clean[number]["lap_end_time_ms"],
                other_clean[number]["lap_end_time_ms"],
            )
            / 1000
            for number in common
        ]
        trend = slope(times, lap_gaps)
        closing = -trend if trend is not None else None
        age = (request.as_of_ms - last["time_ms"]) / 1000 if last else None
        advantage = [
            (other_clean[number]["lap_time_ms"] - own_clean[number]["lap_time_ms"])
            / 1000
            for number in common[-5:]
        ]

        def put(key, value, *, n=None, status="estimated", **kwargs):
            result.put(
                key,
                value,
                focus.id,
                rival.id,
                n=len(points) if n is None else n,
                status=status,
                **kwargs,
            )

        put(
            "rival_timing_gap_s",
            last["gap_s"] if last else None,
            status="observed",
            support={"crossing": last},
        )
        put("rival_gap_observation_age_s", age, status="derived")
        put(
            "rival_mean_timing_gap_s",
            float(np.mean([row["gap_s"] for row in points[-20:]])) if points else None,
        )
        put("rival_closing_rate_s_per_s", closing, n=len(common))
        put(
            "rival_pace_advantage_s_per_lap",
            float(np.median(advantage)) if advantage else None,
            n=len(advantage),
        )
        valid = bool(
            last
            and age <= min(120, pace or 90)
            and clear_interval(data, last["time_ms"], request.as_of_ms)
            and not pit_changed(focus, last["time_ms"], request.as_of_ms)
            and not pit_changed(rival, last["time_ms"], request.as_of_ms)
        )
        projected = last["gap_s"] - (closing or 0) * age if valid else None
        error = max(0.5, (mad(lap_gaps) or 0)) + abs(closing or 0) * (age or 0) * 0.5
        put(
            "rival_projected_gap_s",
            projected,
            bounds=band(projected, error) if projected is not None else None,
            support={"anchor_age_s": age, "trend_available": closing is not None},
            warnings=[
                "Conditional constant closing-rate projection; bounds are sensitivity, not calibrated coverage."
            ],
        )
        put(
            "rival_catch_time_s",
            (
                projected / closing
                if projected is not None
                and projected > 0
                and closing is not None
                and closing > 1e-6
                else None
            ),
        )
        put(
            "rival_crossings_inside_2s_pct",
            (
                100 * sum(0 < row["gap_s"] <= 2 for row in points) / len(points)
                if points
                else None
            ),
            status="derived",
        )
        distance = np.linalg.norm(coordinates[focus.id] - coordinates[rival.id], axis=1)
        finite = np.isfinite(distance)
        put(
            "rival_mean_euclidean_distance_m",
            float(np.mean(distance[finite])) if np.any(finite) else None,
            n=int(np.sum(finite)),
        )
        put(
            "rival_min_euclidean_distance_m",
            float(np.min(distance[finite])) if np.any(finite) else None,
            n=int(np.sum(finite)),
        )
        put(
            "rival_pair_coverage_pct",
            float(np.sum(finite)) / max(1, len(clock)) * 100,
            n=len(clock),
            status="derived",
        )
        arc = progress[rival.id] - progress[focus.id] if progress else np.array([])
        put(
            "rival_arc_ahead_m",
            float(arc[-1]) if len(arc) and np.isfinite(arc[-1]) else None,
        )
        put(
            "rival_mean_arc_ahead_m",
            float(np.nanmean(arc)) if np.any(np.isfinite(arc)) else None,
            n=int(np.sum(np.isfinite(arc))),
        )
        pair_state[rival.id] = dict(
            gap=projected,
            error=error,
            anchor_time_ms=last["time_ms"] if last else None,
            closing_rate=closing,
            pace_advantage=float(np.median(advantage)) if advantage else None,
        )
    return series, pair_state
