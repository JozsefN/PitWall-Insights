"""Reference-racing-line projection. This is deliberately not a track boundary."""

import numpy as np
from scipy.spatial import cKDTree
from .common import numeric, weights


class ReferenceLine:
    def __init__(
        self,
        points,
        *,
        lap_id=None,
        entry_id=None,
        sample_times_ms=None,
        lap_duration_ms=None
    ):
        points = np.asarray(points, dtype=float)
        sample_times = (
            np.asarray(sample_times_ms, dtype=float)
            if sample_times_ms is not None
            else None
        )
        if (
            points.ndim != 2
            or points.shape[1] != 2
            or len(points) < 20
            or not np.all(np.isfinite(points))
        ):
            raise ValueError("A reference line needs at least twenty finite XY points")
        keep = np.r_[True, np.linalg.norm(np.diff(points, axis=0), axis=1) > 0.01]
        if sample_times is not None:
            sample_times = (
                sample_times[keep] if len(sample_times) == len(points) else None
            )
        points = points[keep]
        if len(points) < 20 or np.linalg.norm(points[-1] - points[0]) > 150:
            raise ValueError(
                "Reference lap is incomplete or has an excessive closure gap"
            )
        if np.linalg.norm(points[-1] - points[0]) < 0.01:
            points = points[:-1]
            if sample_times is not None:
                sample_times = sample_times[:-1]
        self.points = points
        self.next = np.roll(points, -1, axis=0)
        self.vectors = self.next - points
        self.segment_lengths = np.linalg.norm(self.vectors, axis=1)
        self.arcs = np.r_[0, np.cumsum(self.segment_lengths[:-1])]
        self.length = float(np.sum(self.segment_lengths))
        if not 500 <= self.length <= 15000 or np.max(self.segment_lengths) > 300:
            raise ValueError("Reference length or gaps are not plausible for a circuit")
        self.tree = cKDTree(points)
        self.lap_id = lap_id
        self.entry_id = entry_id
        self.sample_times_ms = (
            sample_times
            if sample_times is not None
            and np.all(np.isfinite(sample_times))
            and np.all(np.diff(sample_times) > 0)
            else None
        )
        self.lap_duration_ms = (
            lap_duration_ms
            if lap_duration_ms is not None and lap_duration_ms > 0
            else None
        )

    def forward_time_s(self, start_pct, end_pct):
        if self.sample_times_ms is None or self.lap_duration_ms is None:
            return None
        if self.sample_times_ms[-1] - self.sample_times_ms[0] >= self.lap_duration_ms:
            return None
        arc = np.r_[self.arcs, self.length]
        times = np.r_[
            self.sample_times_ms, self.sample_times_ms[0] + self.lap_duration_ms
        ]
        start = float(np.interp(start_pct / 100 * self.length, arc, times))
        end = float(np.interp(end_pct / 100 * self.length, arc, times))
        return (end - start) % self.lap_duration_ms / 1000

    def project(self, points):
        points = np.asarray(points, dtype=float).reshape(-1, 2)
        if not len(points):
            return np.array([]), np.array([])
        _, nearest = self.tree.query(points, k=min(3, len(self.points)))
        if nearest.ndim == 1:
            nearest = nearest[:, None]
        candidates = np.concatenate([nearest, (nearest - 1) % len(self.points)], axis=1)
        starts = self.points[candidates]
        vectors = self.vectors[candidates]
        denominator = np.maximum(self.segment_lengths[candidates] ** 2, 1e-12)
        alpha = np.clip(
            np.sum((points[:, None, :] - starts) * vectors, axis=2) / denominator, 0, 1
        )
        projected = starts + alpha[:, :, None] * vectors
        distances = np.linalg.norm(points[:, None, :] - projected, axis=2)
        best = np.argmin(distances, axis=1)
        rows = np.arange(len(points))
        distance = distances[rows, best]
        along = (
            self.arcs[candidates[rows, best]]
            + alpha[rows, best] * self.segment_lengths[candidates[rows, best]]
        )
        return distance, along / self.length * 100


def position_arrays(entry, data, request):
    times = numeric(entry.positions, "session_time_ms")
    # FastF1's 2020+ XY/Z source coordinates are decimetres, not metres.
    xy = (
        np.column_stack([numeric(entry.positions, "x"), numeric(entry.positions, "y")])
        * 0.1
    )
    usable = np.all(np.isfinite(xy), axis=1) & np.any(xy != 0, axis=1)
    duration = weights(
        times, data.start_ms, data.end_ms, request.options.max_sample_gap_ms
    )
    dt = np.diff(times) / 1000
    delta = np.diff(xy, axis=0)
    distance = np.linalg.norm(delta, axis=1)
    continuous = (
        (dt > 0)
        & (dt <= request.options.max_sample_gap_ms / 1000)
        & usable[:-1]
        & usable[1:]
    )
    speed = np.full(len(dt), np.nan)
    speed[continuous] = distance[continuous] / dt[continuous] * 3.6
    jumps = continuous & (speed > request.options.max_plausible_speed_kph)
    valid = continuous & ~jumps
    speed[~valid] = np.nan
    return times, xy, usable, duration, dt, delta, distance, speed, valid, jumps


def aligned_xy(entry, times, request):
    source_times = numeric(entry.positions, "session_time_ms")
    output = np.full((len(times), 2), np.nan)
    if len(source_times) < 2:
        return output
    xy = (
        np.column_stack([numeric(entry.positions, "x"), numeric(entry.positions, "y")])
        * 0.1
    )
    upper = np.clip(
        np.searchsorted(source_times, times, side="right"), 1, len(source_times) - 1
    )
    lower = upper - 1
    gap = source_times[upper] - source_times[lower]
    valid = (
        (times >= source_times[0])
        & (times <= source_times[-1])
        & (gap > 0)
        & (gap <= request.options.max_sample_gap_ms)
    )
    valid &= np.all(np.isfinite(xy[upper]), axis=1) & np.all(
        np.isfinite(xy[lower]), axis=1
    )
    valid &= np.any(xy[upper] != 0, axis=1) & np.any(xy[lower] != 0, axis=1)
    movement = np.linalg.norm(xy[upper] - xy[lower], axis=1)
    valid &= (
        movement / np.maximum(gap / 1000, 1e-9) * 3.6
        <= request.options.max_plausible_speed_kph
    )
    alpha = (times[valid] - source_times[lower[valid]]) / gap[valid]
    output[valid] = xy[lower[valid]] + alpha[:, None] * (
        xy[upper[valid]] - xy[lower[valid]]
    )
    return output
