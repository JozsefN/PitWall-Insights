"""Causal rival evidence and comparable lap/sector timing for replay."""

from math import exp
from statistics import median

from ..race_estimation.common import number
from ..race_estimation.racing import TimingHistory
from ..source_clock import timed_rows
from ..strategy.common import clean_laps, mad, phase_at
from ..strategy.pits import latest_pit_transitions
from .pace import rain_state
from .pit import comparable_stop_excess

PIT_MEMORY_MS = 360_000
FRESH_MS = 9000
STOP_OPPORTUNITY_MS = 150_000
SECTORS = ("sector_1_time_ms", "sector_2_time_ms", "sector_3_time_ms")


class RaceTiming:
    def __init__(self, details, origin):
        self.intervals = TimingHistory(timed_rows(details.get("intervals"), origin))
        self.ranks = TimingHistory(timed_rows(details.get("race_positions"), origin))

    def gaps(self, entries, stamp):
        gaps, headways = {}, {}
        for entry in entries:
            car = entry.car_number
            rank = self.ranks.at(car, stamp)
            row = self.intervals.at(car, stamp)
            if rank and rank.get("position") == 1:
                gaps[entry.id] = 0.0
            elif row and stamp - row["session_time_ms"] <= FRESH_MS:
                gap = number(row.get("gap_to_leader"))
                headways[entry.id] = number(row.get("interval"))
                if gap is not None and gap >= 0:
                    gaps[entry.id] = gap
        return gaps, headways


def lap_comparison(own_laps, rival_laps):
    """Own minus rival. Shared lap numbers and no more than 35 s apart."""
    by_lap = {row["lap_number"]: row for row in rival_laps}
    pairs = [
        (row, peer)
        for row in own_laps
        if (peer := by_lap.get(row["lap_number"]))
        and abs(row["lap_end_time_ms"] - peer["lap_end_time_ms"]) <= 35_000
    ][-5:]
    if len(pairs) < 3:
        return None
    lap_deltas = [
        (own["lap_time_ms"] - rival["lap_time_ms"]) / 1000 for own, rival in pairs
    ]
    sectors = []
    for key in SECTORS:
        splits = [
            (own[key] - rival[key]) / 1000
            for own, rival in pairs
            if number(own.get(key)) is not None
            and own[key] > 0
            and number(rival.get(key)) is not None
            and rival[key] > 0
        ]
        sectors.append(
            {
                "delta_s": median(splits) if len(splits) >= 3 else None,
                "laps": len(splits),
            }
        )
    return {
        "lap_delta_s": median(lap_deltas),
        "scatter_s": mad(lap_deltas),
        "laps": len(pairs),
        "last_lap": pairs[-1][0]["lap_number"],
        "sectors": sectors,
    }


def following_cost(entry, clean, timing, drift):
    """Age-adjusted own laps on the current set, with reported headways."""
    if not clean or clean[-1].get("stint_number") is None:
        return None
    same = [
        row
        for row in clean
        if row.get("stint_number") == clean[-1]["stint_number"]
        and row.get("compound") == clean[-1].get("compound")
        and row.get("tyre_life") is not None
    ][-10:]
    close, clear = [], []
    for row in same:
        begin = row.get("lap_start_time_ms")
        end = row["lap_end_time_ms"]
        if begin is None or end <= begin:
            continue
        samples = [
            gap
            for item in timing.intervals.between(entry.car_number, begin, end - 1000)
            if (gap := number(item.get("interval"))) is not None and gap > 0
        ]
        if len(samples) < max(5, (end - begin) / 9000):
            continue
        value = row["lap_time_ms"] / 1000 - drift * row["tyre_life"]
        if sum(gap <= 1.2 for gap in samples) / len(samples) >= 0.6:
            close.append(value)
        if sum(gap > 2 for gap in samples) / len(samples) >= 0.8:
            clear.append(value)
    if len(close) < 2 or len(clear) < 2:
        return None
    delta = median(close) - median(clear)
    scatter = max(mad(close), mad(clear), 0.15)
    return {
        "effect_s_lap": max(0, delta) if delta > scatter else 0,
        "close_laps": len(close),
        "clear_laps": len(clear),
        "scatter_s": scatter,
    }


def replay_rivals(
    data, cutoff, timing, gaps, pit_reports, standings, profiles, excluded=()
):
    eligible = [entry for entry in data.entries if entry.id not in excluded]
    clean = {entry.id: clean_laps(entry, cutoff)[-12:] for entry in eligible}
    anchors = {}
    stable_stops = [
        report
        for report in pit_reports
        if report["known_at_ms"] <= cutoff
        and phase_at(data, report["event_time_ms"]) == "1"
        and rain_state(data, report["event_time_ms"]) is False
    ]
    for report in pit_reports:
        end = report["known_at_ms"]
        if not cutoff - PIT_MEMORY_MS <= end <= cutoff:
            continue
        old = anchors.get(report["entry_id"])
        if old is None or report["event_time_ms"] > old[0]:
            before = (
                report["event_time_ms"]
                - 5000
                - round((report.get("lane_duration_s") or 0) * 1000)
            )
            prior, _ = timing.gaps(eligible, before)
            anchors[report["entry_id"]] = (report["event_time_ms"], prior)
    recent_stops = {}
    for entry in eligible:
        entered, exited = latest_pit_transitions(entry, cutoff)
        if not 0 <= entered < exited <= cutoff - FRESH_MS:
            continue
        matches = [
            report
            for report in stable_stops
            if report["entry_id"] == entry.id
            and cutoff - STOP_OPPORTUNITY_MS <= report["known_at_ms"]
            and entered - FRESH_MS <= report["event_time_ms"] <= exited + FRESH_MS
        ]
        if matches:
            measured = comparable_stop_excess(matches[-1], stable_stops)
            if measured and measured["excess_s"] >= max(1.0, measured["scatter_s"]):
                recent_stops[entry.id] = measured
    rivals, traffic = {}, {}
    for entry in eligible:
        current = clean[entry.id]
        profile = profiles.get(current[-1].get("compound")) if current else None
        traffic[entry.id] = following_cost(
            entry, current, timing, (profile or {}).get("drift_s_lap", 0)
        )
        candidates = []
        for rival in eligible:
            if rival.id == entry.id:
                continue
            peer = clean[rival.id]
            comparison = lap_comparison(current, peer)
            gap = _difference(gaps, entry.id, rival.id)
            anchor_age, pre_pit_gap = _prepit_gap(anchors, entry.id, rival.id, cutoff)
            profile_rank = standings.get(entry.car_number)
            rival_rank = standings.get(rival.car_number)
            rank_delta = (
                abs(profile_rank[0] - rival_rank[0])
                if profile_rank and rival_rank
                else None
            )
            grid_delta = (
                abs(entry.grid_position - rival.grid_position)
                if entry.grid_position and rival.grid_position
                else None
            )
            if not (
                (gap is not None and abs(gap) <= 12)
                or (pre_pit_gap is not None and abs(pre_pit_gap) <= 8)
                or (
                    comparison
                    and abs(comparison["lap_delta_s"]) <= 0.45
                    and gap is not None
                    and abs(gap) <= 28
                )
                or (
                    len(current) < 3
                    and gap is None
                    and rank_delta is not None
                    and rank_delta <= 3
                    and grid_delta is not None
                    and grid_delta <= 4
                )
            ):
                continue
            proximity = exp(-abs(gap) / 8) if gap is not None else 0
            pit_memory = (
                exp(-abs(pre_pit_gap) / 8) * exp(-anchor_age / 240)
                if pre_pit_gap is not None
                else 0
            )
            pace = exp(-abs(comparison["lap_delta_s"]) / 0.65) if comparison else 0
            championship = exp(-rank_delta / 5) if rank_delta is not None else 0
            if (
                profile_rank
                and rival_rank
                and number(profile_rank[1]) is not None
                and number(rival_rank[1]) is not None
            ):
                championship = (
                    championship + exp(-abs(profile_rank[1] - rival_rank[1]) / 50)
                ) / 2
            grid = exp(-grid_delta / 5) if grid_delta is not None else 0
            # Numerical relevance score for ordering candidates. Not a probability.
            score = (
                0.56 * max(proximity, pit_memory)
                + 0.31 * pace
                + 0.09 * championship
                + 0.04 * grid
            )
            candidates.append(
                {
                    "entry_id": rival.id,
                    "relevance": score,
                    "gap_s": gap,
                    "pre_pit_gap_s": pre_pit_gap,
                    "pit_memory_seconds": anchor_age,
                    "championship_before": rival_rank,
                    "grid_gap": grid_delta,
                    "recent_slow_stop": (
                        recent_stops.get(rival.id) if pre_pit_gap is not None else None
                    ),
                    "comparison": comparison,
                }
            )
        rivals[entry.id] = sorted(
            candidates, key=lambda row: (-row["relevance"], row["entry_id"])
        )[:4]
    return rivals, traffic


def _difference(gaps, own, rival):
    return gaps[own] - gaps[rival] if own in gaps and rival in gaps else None


def _prepit_gap(anchors, own, rival, cutoff):
    times = sorted(
        (anchors[key] for key in (own, rival) if key in anchors),
        key=lambda row: row[0],
        reverse=True,
    )
    for stamp, prior in times:
        gap = _difference(prior, own, rival)
        if gap is not None and abs(gap) <= 8:
            return max(0, (cutoff - stamp) / 1000), gap
    return None, None
