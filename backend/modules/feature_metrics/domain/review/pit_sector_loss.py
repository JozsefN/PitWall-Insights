"""Estimate net pit loss with matched timing points on either side of the lane."""

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from statistics import median

from .intervention import intervention, is_race_green, warning_kind


@dataclass(frozen=True)
class PitSector:
    entry_id: str
    lap: int
    begin_ms: int
    end_ms: int
    time_s: float
    out_lap: bool


def sector_windows(entry_id, laps, out_laps):
    """Use S3 on the approach lap and S1 on the next lap, with continuous clocks."""
    by_lap = {row["lap_number"]: row for row in laps}
    for number, approach in by_lap.items():
        departure = by_lap.get(number + 1)
        if number < 3 or not departure or number in out_laps:
            continue
        if any(
            row.get("is_generated") or row.get("is_deleted")
            for row in (approach, departure)
        ):
            continue
        one, two, three = (approach.get(f"sector_{n}_time_ms") for n in (1, 2, 3))
        exit_split = departure.get("sector_1_time_ms")
        start, next_start = approach.get("lap_start_time_ms"), departure.get(
            "lap_start_time_ms"
        )
        if (
            start is None
            or next_start is None
            or not all(
                value and 5000 < value < 150000
                for value in (one, two, three, exit_split)
            )
        ):
            continue
        if abs(start + one + two + three - next_start) > 1500:
            continue
        yield PitSector(
            entry_id,
            number,
            start + one + two,
            next_start + exit_split,
            (three + exit_split) / 1000,
            number + 1 in out_laps,
        )


def pit_sector_losses(windows, reports, controls, cutoff):
    phases = [(0, "green")]
    yellows = []
    for row in sorted(controls, key=lambda item: item["session_time_ms"]):
        stamp = row["session_time_ms"]
        if stamp > cutoff:
            break
        phase = intervention(row) or ("green" if is_race_green(row) else None)
        if phase and phase != phases[-1][1]:
            phases.append((stamp, phase))
        if warning_kind(row) in ("yellow", "double_yellow"):
            yellows.append(stamp)
    times = [stamp for stamp, _ in phases]
    known = {
        (row["entry_id"], row["lap_number"]): row
        for row in reports
        if row["known_at_ms"] <= cutoff
    }
    references, visits = defaultdict(list), []
    for window in windows:
        if window.end_ms > cutoff:
            continue
        left = bisect_right(times, window.begin_ms) - 1
        right = bisect_right(times, window.end_ms) - 1
        phase = phases[left][1]
        if left != right or phase == "red":
            continue
        if phase == "green":
            yellow = bisect_right(yellows, window.begin_ms - 15000)
            if yellow < len(yellows) and yellows[yellow] <= window.end_ms:
                continue
        report = known.get((window.entry_id, window.lap))
        if window.out_lap and report:
            if window.begin_ms <= report["event_time_ms"] <= window.end_ms:
                visits.append((phase, window, report))
        elif not window.out_lap and not report:
            references[phase].append(window)

    output = []
    for phase, window, report in visits:
        nearby = sorted(
            (abs(peer.begin_ms - window.begin_ms), peer.entry_id, peer.lap, peer.time_s)
            for peer in references[phase]
            if peer.entry_id != window.entry_id
            and abs(peer.begin_ms - window.begin_ms) <= 100_000
        )
        by_driver = {}
        for _, driver, _, time in nearby:
            by_driver.setdefault(driver, time)
        if len(by_driver) < 3:
            continue
        peers = list(by_driver.values())[:7]
        net = window.time_s - median(peers)
        if 0 < net < 65:
            output.append(
                {
                    **report,
                    "phase": phase,
                    "net_loss_s": net,
                    "stop_lap_end_ms": window.end_ms,
                    "peer_count": len(peers),
                }
            )
    return output


def session_pit_sectors(data, reports):
    marked = defaultdict(set)
    for row in reports:
        if row.get("out_lap_reported") and row["known_at_ms"] <= data.end_ms:
            marked[row["entry_id"]].add(row["lap_number"] + 1)
    windows = (
        window
        for entry in data.entries
        for window in sector_windows(
            entry.id,
            entry.laps,
            marked[entry.id]
            | {
                row["lap_number"]
                for row in entry.laps
                if row.get("pit_out_time_ms") is not None
            },
        )
    )
    return pit_sector_losses(windows, reports, data.race_control, data.end_ms)
