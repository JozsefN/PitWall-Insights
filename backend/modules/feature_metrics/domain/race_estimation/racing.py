"""Native timing evidence for battles and sustained changes of order."""

from bisect import bisect_right
from dataclasses import replace
from statistics import median

from .common import event, number, phase_at

BATTLE_GAP_S = 1.2


class TimingHistory:
    def __init__(self, rows):
        grouped = {}
        for row in rows:
            grouped.setdefault(row["driver_number"], {})[row["session_time_ms"]] = row
        self.rows = {car: sorted(items) for car, items in grouped.items()}
        self.values = {
            car: [items[t] for t in self.rows[car]] for car, items in grouped.items()
        }

    def at(self, car, stamp):
        index = bisect_right(self.rows.get(car, []), stamp) - 1
        return self.values[car][index] if index >= 0 else None

    def between(self, car, start, end):
        clocks = self.rows.get(car, [])
        return self.values.get(car, [])[
            bisect_right(clocks, start - 1) : bisect_right(clocks, end)
        ]


def rank(row):
    return number(row.get("position")) if row else None


def clean_running(data, context, cars, start, end):
    if phase_at(data.track_status, start) != "1" or any(
        start < row["session_time_ms"] <= end and str(row["status"]) != "1"
        for row in data.track_status
    ):
        return False
    if any(
        start - 30000 <= row["session_time_ms"] <= end and row["driver_number"] in cars
        for row in context.pits
    ):
        return False
    ids = {context.driver_ids.get(car) for car in cars}
    for entry in data.entries:
        if entry.id not in ids:
            continue
        boundaries = sorted(
            (lap[key], key)
            for lap in entry.laps
            for key in ("pit_in_time_ms", "pit_out_time_ms")
            if lap.get(key) is not None
        )
        if any(start - 5000 <= stamp <= end for stamp, _ in boundaries):
            return False
        prior = [key for stamp, key in boundaries if stamp < start]
        if prior and prior[-1] == "pit_in_time_ms":
            return False
    return True


def race_finished(data, cutoff):
    return any(
        row["session_time_ms"] <= cutoff
        and (
            "CHEQUERED" in str(row.get("flag") or "").upper()
            or "SESSION FINISHED" in str(row.get("message") or "").upper()
        )
        for row in data.race_control
    )


def completed_passes(data, context, request, ranks, gaps):
    """Confirm timing evidence after a hold interval. Timing cannot establish contact."""
    delay = request.assumptions.source_report_delay_ms
    output = []
    seen = {}
    for row in context.overtakes:
        stamp = row["session_time_ms"]
        known = stamp + 12000 + delay
        if not data.start_ms <= known <= request.as_of_ms or race_finished(data, known):
            continue
        passer = str(row.get("overtaking_driver_number"))
        passed = str(row.get("overtaken_driver_number"))
        if passer == passed or any(
            car not in context.driver_ids for car in (passer, passed)
        ):
            continue
        before = [rank(ranks.at(car, stamp - 1500)) for car in (passer, passed)]
        after = [rank(ranks.at(car, stamp + 12000)) for car in (passer, passed)]
        if (
            None in before + after
            or before[0] - before[1] != 1
            or after[1] - after[0] != 1
        ):
            continue
        crossings = sorted(
            {
                stamp + 5000,
                stamp + 12000,
                *(
                    value["session_time_ms"]
                    for car in (passer, passed)
                    for value in ranks.between(car, stamp + 5000, stamp + 12000)
                ),
            }
        )
        if any(
            (a := rank(ranks.at(passer, time))) is None
            or (b := rank(ranks.at(passed, time))) is None
            or a >= b
            for time in crossings
        ):
            continue
        predecessor_gap = gaps.at(passer, stamp - 1500)
        successor_gap = gaps.at(passed, stamp + 12000)
        if not predecessor_gap or not successor_gap:
            continue
        if any(
            "LAP" in str(item.get("gap_to_leader") or "").upper()
            for item in (predecessor_gap, successor_gap)
        ):
            continue
        gap_before = number(predecessor_gap.get("interval"))
        gap_after = number(successor_gap.get("interval"))
        if (
            gap_before is None
            or gap_after is None
            or not (0 <= gap_before <= 1.5 and 0 <= gap_after <= 2.0)
        ):
            continue
        if (
            stamp - predecessor_gap["session_time_ms"] > 9500
            or stamp + 12000 - successor_gap["session_time_ms"] > 8000
        ):
            continue
        # Later pit reports must not retroactively change an already visible event.
        visible = [
            pit
            for pit in context.pits
            if pit.get("known_at_ms", pit["session_time_ms"] + delay) <= known
        ]
        if not clean_running(
            data,
            replace(context, pits=visible),
            (passer, passed),
            stamp - 8000,
            stamp + 12000,
        ):
            continue
        key = (passer, passed)
        if stamp - seen.get(key, -60000) < 15000:
            continue
        seen[key] = stamp
        output.append(
            event(
                "overtake",
                context.driver_ids[passer],
                stamp,
                known,
                "On-track pass estimate",
                "The provider reported a position change. Adjacent drivers swapped order, remained in that order and showed close gaps before and after during green running.",
                rival=context.driver_ids[passed],
                classification="candidate",
                severity="info",
                support=0.85,
                evidence={
                    "source": "overtakes + position + intervals",
                    "rank_before": before,
                    "rank_after": after,
                    "gap_before_s": gap_before,
                    "gap_after_s": gap_after,
                    "hold_s": 12,
                },
                alternatives=[
                    "Unreported pit activity or timing correction",
                    "The exact passing location is unresolved",
                ],
            )
        )
    return output


def battle_snapshot(data, context, request):
    ranks = TimingHistory(context.positions)
    gaps = TimingHistory(context.intervals)
    cutoff = request.as_of_ms - request.assumptions.source_report_delay_ms
    rows = []
    order = {car: rank(ranks.at(car, cutoff)) for car in context.driver_ids}
    for follower, place in order.items():
        if place is None or place < 2:
            continue
        leaders = [car for car, position in order.items() if position == place - 1]
        if len(leaders) != 1 or list(order.values()).count(place) != 1:
            continue
        leader = leaders[0]
        points = []
        for row in reversed(gaps.between(follower, cutoff - 30000, cutoff)):
            stamp = row["session_time_ms"]
            value = number(row.get("interval"))
            if (
                value is None
                or not 0 < value <= 10
                or rank(ranks.at(follower, stamp)) != place
                or rank(ranks.at(leader, stamp)) != place - 1
                or (points and points[-1][0] - stamp > 8000)
            ):
                break
            points.append((stamp, value))
        points.reverse()
        if len(points) < 3 or cutoff - points[-1][0] > 8000:
            continue
        if race_finished(data, cutoff) or not clean_running(
            data, context, (follower, leader), points[0][0], cutoff
        ):
            continue
        span = (points[-1][0] - points[0][0]) / 1000
        if span < 8:
            continue
        changes = [left[1] - right[1] for left, right in zip(points, points[1:])]
        consistent = (
            len(points) >= 4
            and span >= 12
            and sum(delta > 0.02 for delta in changes) / len(changes) >= 0.75
            and points[0][1] - points[-1][1] >= 0.15
        )
        close = (
            points[-1][1] <= BATTLE_GAP_S
            and sum(gap <= BATTLE_GAP_S for _, gap in points) / len(points) >= 0.75
        )
        rows.append(
            {
                "follower_id": context.driver_ids[follower],
                "ahead_id": context.driver_ids[leader],
                "active_battle": close,
                "consistent_closing": consistent,
                "span_s": span,
                "sample_count": len(points),
                "gap_s": points[-1][1],
                "mean_gap_s": sum(
                    (a[1] + b[1]) / 2 * (b[0] - a[0])
                    for a, b in zip(points, points[1:])
                )
                / (span * 1000),
                "closing_s_per_s": (
                    median(
                        changes[i] / ((b[0] - a[0]) / 1000)
                        for i, (a, b) in enumerate(zip(points, points[1:]))
                    )
                    if consistent
                    else None
                ),
            }
        )
    return rows, completed_passes(data, context, request, ranks, gaps)
