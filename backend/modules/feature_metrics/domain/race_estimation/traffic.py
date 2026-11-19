"""Traffic is inferred from timestamped timing reports, never Euclidean nearest cars."""

import math
from .common import Cursor, number, slope, clamp, at


def wake_loss(distance_m, assumptions):
    if distance_m is None:
        return None
    exponent = clamp(-(distance_m - 10) / assumptions.wake_decay_m, -60, 10)
    return min(
        assumptions.max_wake_loss_pct,
        assumptions.wake_loss_at_10m_pct * math.exp(exponent),
    )


class TrafficContext:
    def __init__(self, context, request):
        self.context, self.request = context, request
        self.intervals = {}
        self.ranks = {}
        for row in context.intervals:
            self.intervals.setdefault(row["driver_number"], []).append(row)
        for row in context.positions:
            self.ranks.setdefault(row["driver_number"], []).append(row)
        self.interval_cursors = {
            car: Cursor(rows) for car, rows in self.intervals.items()
        }
        self.rank_cursors = {car: Cursor(rows) for car, rows in self.ranks.items()}

    def snapshot(self, time_ms):
        settings = self.request.assumptions
        # Native timestamps are event time; apply an explicit availability margin.
        cutoff = time_ms - settings.source_report_delay_ms
        ranks = {}
        for car, cursor in self.rank_cursors.items():
            # Position reports are state-change events: unchanged rank does not expire.
            row = cursor.get(cutoff)
            if row and number(row.get("position")) is not None:
                ranks[car] = int(row["position"])
        by_rank = {rank: car for car, rank in ranks.items()}
        output = {}
        for car, cursor in self.interval_cursors.items():
            row = cursor.get(cutoff, settings.max_report_age_ms)
            if not row:
                continue
            raw = row.get("interval")
            gap = number(raw)
            rank = ranks.get(car)
            ahead_car = by_rank.get(rank - 1) if rank is not None and rank > 1 else None
            # Rank 1 has no car ahead; lap-difference reports are never a close gap.
            if rank == 1:
                gap = None
            output[car] = {
                "gap_s": gap if gap is not None and 0 <= gap <= 120 else None,
                "ahead_id": self.context.driver_ids.get(ahead_car),
                "ahead_number": ahead_car,
                "lapped": isinstance(raw, str) and "lap" in raw.lower(),
                "report_time_ms": row["session_time_ms"],
                "rank": rank,
            }
        return output

    def recent_trend(self, car, cutoff):
        settings = self.request.assumptions
        points = [
            (row["session_time_ms"], number(row.get("interval")))
            for row in self.intervals.get(car, [])
            if cutoff - 30000
            <= row["session_time_ms"]
            <= cutoff - settings.source_report_delay_ms
        ]
        points = [(t, v) for t, v in points if v is not None and 0 < v < 120]
        # Big timing corrections, lapping and rank changes are not a closing-speed model.
        if (
            len(points) < 3
            or cutoff - points[-1][0]
            > settings.max_report_age_ms + settings.source_report_delay_ms
            or any(abs(b[1] - a[1]) > 2 for a, b in zip(points, points[1:]))
        ):
            return None, 0.0
        initial = at(self.ranks.get(car, []), points[0][0])
        ranks = ([initial.get("position")] if initial else []) + [
            row.get("position")
            for row in self.ranks.get(car, [])
            if points[0][0]
            <= row["session_time_ms"]
            <= cutoff - settings.source_report_delay_ms
        ]
        if len(set(ranks)) > 1:
            return None, 0.0
        if ranks:
            rank = number(ranks[-1])
            # A different car can become the target while this driver's own rank stays unchanged.
            targets = set()
            for stamp, _ in points:
                candidates = [
                    other
                    for other, rows in self.ranks.items()
                    if (row := at(rows, stamp))
                    and number(row.get("position")) == rank - 1
                ]
                if len(candidates) != 1:
                    return None, 0.0
                targets.add(candidates[0])
            if len(targets) > 1:
                return None, 0.0
        value = slope(points)
        return (
            (-value, clamp(len(points) / 8) * 0.75)
            if value is not None
            else (None, 0.0)
        )
