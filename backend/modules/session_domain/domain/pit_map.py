"""Reconstruct the pit lane from timed visits or observed pit traversals."""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil, hypot
from statistics import median

import numpy as np
from scipy.spatial import cKDTree

Point = tuple[float, float]  # OpenF1 map units, decimetres
APPROACH_PAD_MS = 2500
PIT_HINT_RADIUS_MS = 65_000
DEPARTURE_DISTANCE = 95  # 9.5 m from a fast lap in the same telemetry frame


@dataclass(frozen=True)
class PitReport:
    entry_id: str
    team_id: str | None
    lap_number: int
    time_ms: int
    lane_ms: int
    stationary_s: float | None


@dataclass(frozen=True)
class PitFix:
    time_ms: int
    point: Point


@dataclass(frozen=True)
class PitTraceWindow:
    entry_id: str
    team_id: str | None
    lap_number: int
    start_ms: int
    end_ms: int
    timed_crossings: bool = False


def pit_position_windows(
    reports: list[PitReport], hints: Sequence[PitTraceWindow] = (),
) -> list[tuple[str, int, int]]:
    """Return disjoint, inclusive sample windows for each driver."""
    windows = [
        (report.entry_id,
         max(0, report.time_ms - report.lane_ms - APPROACH_PAD_MS),
         report.time_ms + report.lane_ms + APPROACH_PAD_MS)
        for report in reports
    ]
    windows.extend(
        (hint.entry_id, max(0, hint.start_ms - APPROACH_PAD_MS), hint.end_ms + APPROACH_PAD_MS)
        for hint in hints
    )
    merged: list[tuple[str, int, int]] = []
    for entry, start, end in sorted(windows):
        if merged and merged[-1][0] == entry and start <= merged[-1][2] + 1:
            _, previous_start, previous_end = merged[-1]
            merged[-1] = (entry, previous_start, max(previous_end, end))
        else:
            merged.append((entry, start, end))
    return merged


@dataclass(frozen=True)
class Stopped:
    start_ms: int
    end_ms: int
    point: Point


@dataclass(frozen=True)
class PitPass:
    report: PitReport
    start_ms: int
    end_ms: int
    path: tuple[PitFix, ...]
    stopped: Stopped | None


def distance(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def contiguous(a: PitFix, b: PitFix) -> bool:
    gap = b.time_ms - a.time_ms
    return 0 < gap <= 2200 and distance(a.point, b.point) <= 1.4 * gap


def representative_point(points: list[Point]) -> Point:
    return median(p[0] for p in points), median(p[1] for p in points)


def find_stop(path: tuple[PitFix, ...], expected_s: float | None) -> Stopped | None:
    """Find a compact dwell followed by movement past the same point."""
    candidates: list[Stopped] = []
    minimum = max(550, 400 * expected_s) if expected_s is not None else 1100
    maximum = 1400 * expected_s + 1600 if expected_s is not None else 35000
    for start, first in enumerate(path[1:-2], 1):
        if distance(first.point, path[start + 1].point) > 16:
            continue
        end = start + 1
        while end < len(path) - 1 and distance(first.point, path[end + 1].point) <= 16:
            end += 1
        span = path[end].time_ms - first.time_ms
        if not minimum <= span <= maximum:
            continue
        if distance(first.point, path[0].point) < 120 or distance(first.point, path[-1].point) < 120:
            continue
        candidates.append(Stopped(first.time_ms, path[end].time_ms, representative_point([fix.point for fix in path[start:end + 1]])))
    if expected_s is not None:
        return min(candidates, key=lambda stop: abs(stop.end_ms - stop.start_ms - expected_s * 1000), default=None)
    return max(candidates, key=lambda stop: stop.end_ms - stop.start_ms, default=None)


def candidate_passes(report: PitReport, fixes: list[PitFix], times: list[int]) -> list[PitPass]:
    # OpenF1 documents the duration but not the exact meaning of the date.
    # Evaluate both timing windows, with the commonly observed pit-out stamp first.
    candidates = []
    for start, end in ((report.time_ms - report.lane_ms, report.time_ms), (report.time_ms, report.time_ms + report.lane_ms)):
        if visit := timed_pass(report, fixes, times, start, end):
            candidates.append(visit)
    return candidates


def timed_pass(report: PitReport, fixes: list[PitFix], times: list[int], start: int, end: int) -> PitPass | None:
    path = tuple(fixes[bisect_left(times, start):bisect_right(times, end)])
    if len(path) < 9 or path[0].time_ms - start > 1500 or end - path[-1].time_ms > 1500:
        return None
    if any(not contiguous(a, b) for a, b in zip(path, path[1:])):
        return None
    length = sum(distance(a.point, b.point) for a, b in zip(path, path[1:]))
    if distance(path[0].point, path[-1].point) < 600 or length / report.lane_ms > 0.36:
        return None
    return PitPass(report, start, end, path, find_stop(path, report.stationary_s))


def reference_line(fixes: list[PitFix]) -> cKDTree | None:
    if len(fixes) < 32 or distance(fixes[0].point, fixes[-1].point) > 600:
        return None
    if any(
        not 0 < b.time_ms - a.time_ms <= 2_200
        or distance(a.point, b.point) > max(600, 1.4 * (b.time_ms - a.time_ms))
        for a, b in zip(fixes, fixes[1:])
    ):
        return None
    points = np.asarray([fix.point for fix in fixes] + [fixes[0].point])
    arcs = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    if not 20_000 <= arcs[-1] <= 90_000:
        return None
    # Resampling bounds nearest-point error independently of telemetry density.
    offsets = np.linspace(0, arcs[-1], ceil(arcs[-1] / 20), endpoint=False)
    return cKDTree(np.column_stack([np.interp(offsets, arcs, axis) for axis in points.T]))


def trace_passes(
    window: PitTraceWindow, fixes: list[PitFix], times: list[int], racing_line: cKDTree | None,
) -> list[PitPass]:
    if window.timed_crossings:
        intervals = [(window.start_ms, window.end_ms)]
    elif racing_line is None:
        return []
    else:
        window_fixes = fixes[bisect_left(times, window.start_ms):bisect_right(times, window.end_ms)]
        if len(window_fixes) < 9:
            return []
        distances, _ = racing_line.query([fix.point for fix in window_fixes])
        intervals = []
        departure = None
        for i, (before, after) in enumerate(zip(distances, distances[1:])):
            if not contiguous(window_fixes[i], window_fixes[i + 1]):
                departure = None
            elif before <= DEPARTURE_DISTANCE < after:
                departure = i
            elif before > DEPARTURE_DISTANCE >= after and departure is not None:
                intervals.append((window_fixes[departure].time_ms, window_fixes[i + 1].time_ms))
                departure = None
    candidates = []
    for start, end in intervals:
        if not 5_000 <= end - start <= 180_000:
            continue
        report = PitReport(window.entry_id, window.team_id, window.lap_number, end, end - start, None)
        if visit := timed_pass(report, fixes, times, start, end):
            candidates.append(visit)
    return candidates


def same_lane(first: PitPass, second: PitPass) -> bool:
    if distance(first.path[0].point, second.path[0].point) > 800 or distance(first.path[-1].point, second.path[-1].point) > 800:
        return False
    # Check the middle of the pass as well as its ends. On some tracks the pit
    # lane runs very close to the racing straight at both ends.
    midpoint = second.path[len(second.path) // 2].point
    return min(distance(midpoint, fix.point) for fix in first.path) <= 95


def pit_boxes(visits: list[PitPass]) -> list[dict]:
    by_team = defaultdict(list)
    for visit in visits:
        if visit.stopped and visit.report.team_id:
            by_team[visit.report.team_id].append(visit)

    boxes = []
    for team_id, observations in by_team.items():
        clusters = [
            [other for other in observations if distance(seed.stopped.point, other.stopped.point) <= 65]
            for seed in observations
        ]
        cluster = max(clusters, key=lambda group: (len(group), sum(visit.report.stationary_s is not None for visit in group)))
        confirmed = [visit.end_ms for visit in cluster if visit.report.stationary_s is not None]
        if len(cluster) >= 2:
            confirmed.append(sorted(visit.end_ms for visit in cluster)[1])
        if not confirmed:
            continue
        # Use the first evidence that confirms the box. Later stops may refine
        # the historical estimate without moving the marker during replay.
        known_at = min(confirmed)
        point = representative_point([visit.stopped.point for visit in cluster if visit.end_ms <= known_at])
        boxes.append({"team_id": team_id, "point": point, "known_at_ms": known_at})
    return boxes


def build_pit_map(
    reports: list[PitReport],
    samples: dict[str, list[PitFix]],
    *,
    hints: Sequence[PitTraceWindow] = (),
    racing_line: cKDTree | None = None,
) -> dict:
    indexed = {}
    for entry_id, fixes in samples.items():
        ordered = sorted({fix.time_ms: fix for fix in fixes}.values(), key=lambda fix: fix.time_ms)
        indexed[entry_id] = ordered, [fix.time_ms for fix in ordered]
    if hints:
        passes = [group for hint in hints if hint.entry_id in indexed
                  if (group := trace_passes(hint, *indexed[hint.entry_id], racing_line))]
        # A geometric departure may be an incident. Require independent cars
        # on the same route before using it as circuit geometry.
        timed = {(hint.entry_id, hint.start_ms, hint.end_ms) for hint in hints if hint.timed_crossings}
        references = [candidate for group in passes for candidate in group
                      if (candidate.report.entry_id, candidate.start_ms, candidate.end_ms) in timed]
    else:
        passes = [group for report in reports if report.entry_id in indexed
                  if (group := candidate_passes(report, *indexed[report.entry_id]))]
        references = [candidate for group in passes for candidate in group if candidate.stopped]
    if not references:
        # Drive-throughs and stops without a resolved stationary dwell can
        # establish the lane when two independent cars follow the same route.
        references = [candidate for group in passes for candidate in group if any(
            candidate.report.entry_id != other.report.entry_id and same_lane(candidate, other)
            for adjacent in passes for other in adjacent
        )]
        if not references:
            return {"lane": [], "boxes": [], "visits": []}

    # Use a real, continuous pass as the drawn route. Corroboration across other
    # reports rejects isolated detours and selects the common pit-lane path.
    reference = max(references, key=lambda target: (
        sum(any(same_lane(target, other) for other in group) for group in passes),
        distance(target.path[0].point, target.path[-1].point),
    ))
    visits = []
    seen = set()
    for group in passes:
        matching = [candidate for candidate in group if same_lane(reference, candidate)]
        if matching:
            visit = next((candidate for candidate in matching if candidate.stopped), matching[0])
            key = (visit.report.entry_id, visit.start_ms, visit.end_ms)
            if key not in seen:
                visits.append(visit)
                seen.add(key)
    visits.sort(key=lambda visit: visit.start_ms)
    fixes, times = indexed[reference.report.entry_id]
    first = bisect_left(times, reference.path[0].time_ms)
    last = bisect_left(times, reference.path[-1].time_ms)
    while first > 0 and times[first - 1] >= reference.start_ms - APPROACH_PAD_MS and contiguous(fixes[first - 1], fixes[first]):
        first -= 1
    while last + 1 < len(fixes) and times[last + 1] <= reference.end_ms + APPROACH_PAD_MS and contiguous(fixes[last], fixes[last + 1]):
        last += 1
    path = [fixes[first].point]
    for fix in fixes[first + 1:last]:
        if distance(fix.point, path[-1]) >= 18:
            path.append(fix.point)
    path.append(fixes[last].point)
    return {
        "lane": path,
        "boxes": pit_boxes(visits),
        "visits": [{
            "entry_id": visit.report.entry_id,
            "lap_number": visit.report.lap_number,
            "start_ms": visit.start_ms,
            "end_ms": visit.end_ms,
            "stopped_from_ms": visit.stopped.start_ms if visit.stopped else None,
            "stopped_until_ms": visit.stopped.end_ms if visit.stopped else None,
            "reported_stationary_s": visit.report.stationary_s,
        } for visit in visits],
    }
