"""Timing-line evidence shared by early out-laps and weather crossover."""

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from statistics import median

from ..strategy.common import mad
from .pace import SLICKS

SPLIT_LAG_MS = 1000
PEER_WINDOW_MS = 40_000
FRESH_WINDOW_MS = 145_000
FAMILIES = ("SLICK", "INTERMEDIATE", "WET")


def family(compound):
    return "SLICK" if compound in SLICKS else compound if compound in FAMILIES else None


@dataclass(frozen=True)
class Split:
    driver: str
    lap: int
    sector: int
    end: int
    seconds: float
    compound: str
    outlap: bool
    age: int | None = None

    @property
    def family(self):
        return family(self.compound)


class SectorTiming:
    def __init__(self, raw, snapshot, reports, out_laps):
        self.cutoff = snapshot.end_ms
        self.current = {}
        self.latest = {}
        self.splits = defaultdict(list)
        self.by_driver = defaultdict(list)
        self._offsets = {}
        visits = {
            (row["entry_id"], row["lap_number"] + 1): row
            for row in reports
            if row["out_lap_reported"] and row["known_at_ms"] <= self.cutoff
        }
        published = {
            (row["entry_id"], row["lap_number"]): row["event_time_ms"]
            for row in reports
            if row["known_at_ms"] <= self.cutoff
        }
        raw_by_id = {
            entry.id: {lap["lap_number"]: lap for lap in entry.laps}
            for entry in raw.entries
        }
        flags = sorted(snapshot.track_status, key=lambda row: row["session_time_ms"])
        flag_times = [row["session_time_ms"] for row in flags]
        for entry in snapshot.entries:
            previous = None
            for row in entry.laps:
                lap = row["lap_number"]
                start = row["lap_start_time_ms"]
                complete = row.get("lap_end_time_ms") is not None
                marked = (
                    lap in out_laps.get(entry.id, ())
                    or row.get("pit_out_time_ms") is not None
                )
                report = visits.get((entry.id, lap))
                exit_visible = row.get("pit_out_time_ms")
                if report and abs(report["event_time_ms"] - start) <= 55_000:
                    exit_visible = report["event_time_ms"]
                peek = raw_by_id[entry.id].get(lap, {})
                if marked:
                    compound = (
                        (row if complete else peek).get("compound")
                        if complete or exit_visible is not None
                        else None
                    )
                elif complete:
                    compound = row.get("compound")
                    # The feed occasionally labels the approach lap with the next set.
                    if (entry.id, lap) in published and previous:
                        compound = previous
                else:
                    compound = previous
                if family(compound):
                    self.current[entry.id] = compound
                    self.latest[entry.id] = (row, marked, exit_visible)
                elif marked:
                    self.current.pop(entry.id, None)
                    self.latest.pop(entry.id, None)
                if not family(compound) or row.get("is_deleted"):
                    if complete:
                        previous = compound
                    continue
                for sector in (1, 2, 3):
                    end = row.get(f"sector_{sector}_session_time_ms")
                    length = row.get(f"sector_{sector}_time_ms")
                    if not length or not end or not 3500 <= length <= 100_000:
                        continue
                    begin = end - length
                    if end + SPLIT_LAG_MS > self.cutoff or begin < start - 1000:
                        continue
                    if marked and (
                        sector == 1
                        or (exit_visible is not None and begin < exit_visible)
                    ):
                        continue
                    if sector == 3 and (
                        (entry.id, lap) in published
                        or row.get("pit_in_time_ms") is not None
                    ):
                        continue
                    left = bisect_right(flag_times, begin) - 1
                    right = bisect_right(flag_times, end)
                    if flags and (
                        left < 0
                        or any(flag["status"] != "1" for flag in flags[left:right])
                    ):
                        continue
                    age = (peek if marked and exit_visible is not None else row).get(
                        "tyre_life"
                    )
                    sample = Split(
                        entry.id, lap, sector, end, length / 1000, compound, marked, age
                    )
                    self.splits[sector].append(sample)
                    self.by_driver[entry.id].append(sample)
                if complete:
                    previous = compound
        for samples in self.splits.values():
            samples.sort(key=lambda row: row.end)

    def offsets(self, recent):
        """Learn a driver/sector pace offset under similar tyres and clock times."""
        if recent in self._offsets:
            return self._offsets[recent]
        offsets = defaultdict(list)
        for sector, rows in self.splits.items():
            candidates = [
                s
                for s in rows
                if recent - 650_000 <= s.end < recent - 65_000 and not s.outlap
            ]
            times = [s.end for s in candidates]
            for sample in candidates:
                left = bisect_right(times, sample.end - 30_000)
                right = bisect_right(times, sample.end + 30_000)
                peers = {
                    peer.driver: peer.seconds
                    for peer in candidates[left:right]
                    if peer.driver != sample.driver and peer.family == sample.family
                }
                if len(peers) >= 3:
                    offsets[sample.driver, sector].append(
                        sample.seconds - median(peers.values())
                    )
        result = {
            key: median(values) for key, values in offsets.items() if len(values) >= 3
        }
        self._offsets[recent] = result
        return result

    def warmup_samples(self, since_ms=0):
        """Same compound, timing sector and nearby clock, with settled sets as controls."""
        correction = self.offsets(self.cutoff)
        samples = defaultdict(dict)
        for sector, rows in self.splits.items():
            stamps = [row.end for row in rows]
            indexing = {(row.driver, row.lap): row for row in rows}

            def controls_at(sample):
                left = bisect_right(stamps, sample.end - 30_000)
                right = bisect_right(stamps, sample.end + 30_000)
                return {
                    row.driver: row.seconds - correction.get((row.driver, sector), 0)
                    for row in rows[left:right]
                    if row.driver != sample.driver
                    and not row.outlap
                    and row.compound == sample.compound
                    and (row.age is None or row.age <= 9)
                }

            for cold in rows:
                if not cold.outlap or cold.end < since_ms:
                    continue
                controls = controls_at(cold)
                if len(controls) >= 2:
                    gap = (
                        cold.seconds
                        - correction.get((cold.driver, sector), 0)
                        - median(controls.values())
                    )
                    settled = indexing.get((cold.driver, cold.lap + 1))
                    if (
                        settled
                        and settled.compound == cold.compound
                        and not settled.outlap
                        and 0 < settled.end - cold.end <= 175_000
                    ):
                        later = controls_at(settled)
                        peers = controls.keys() & later.keys()
                        if len(peers) >= 2:
                            grip = median(controls[key] - later[key] for key in peers)
                            gap = cold.seconds - settled.seconds - grip
                    if abs(gap) <= 8:
                        samples[cold.family, sector].setdefault(cold.driver, []).append(
                            gap
                        )
        return {
            key: [median(values) for values in drivers.values()]
            for key, drivers in samples.items()
        }

    def outlap(self, driver, warmup=None):
        latest = self.latest.get(driver)
        if not latest:
            return None
        lap, marked, exit_ms = latest
        if not marked or exit_ms is None or lap.get("lap_end_time_ms") is not None:
            return None
        splits = [
            sample
            for sample in self.by_driver[driver]
            if sample.lap == lap["lap_number"]
        ]
        if not splits or self.cutoff - splits[-1].end > 60_000:
            return None
        actual = splits[-1]
        correction = self.offsets(actual.end)
        peers = {}
        for split in self.splits[actual.sector]:
            if (
                abs(split.end - actual.end) <= PEER_WINDOW_MS
                and split.driver != driver
                and split.family == actual.family
                and not split.outlap
            ):
                peers[split.driver] = split.seconds - correction.get(
                    (split.driver, split.sector), 0
                )
        if len(peers) < 2:
            return {
                "sector": actual.sector,
                "lap": actual.lap,
                "at_ms": actual.end,
                "compound": actual.compound,
                "split_s": actual.seconds,
                "peers": len(peers),
                "loss_s": None,
                "remaining_loss_s": None,
                "scatter_s": None,
            }
        residual = (
            actual.seconds
            - correction.get((driver, actual.sector), 0)
            - median(peers.values())
        )
        scatter = max(0.45, mad(list(peers.values())) or 0)
        expected = (warmup or {}).get((actual.family, actual.sector))
        ordinary = expected["loss_s"] if expected else None
        extra = max(0.0, residual - (ordinary or 0))
        # The elapsed loss is already in the gap. Only extrapolate a fraction to the next sector.
        return {
            "sector": actual.sector,
            "lap": actual.lap,
            "at_ms": actual.end,
            "compound": actual.compound,
            "split_s": actual.seconds,
            "peers": len(peers),
            "loss_s": residual,
            "typical_warmup_s": ordinary,
            "remaining_loss_s": (
                min(3.0, (extra - scatter) / 2)
                if actual.sector < 3 and extra > scatter
                else 0.0
            ),
            "scatter_s": scatter,
        }

    def slick_traction(self):
        """Find simultaneous clear-track slowing against each driver's recent slick pace."""
        changes = []
        for number, rows in self.splits.items():
            samples = [row for row in rows if row.family == "SLICK" and not row.outlap]
            recent = {
                row.driver: row for row in samples if self.cutoff - row.end <= 55_000
            }
            history = defaultdict(list)
            for row in samples:
                if 75_000 <= self.cutoff - row.end <= 360_000:
                    history[row.driver].append(row.seconds)
            deltas = [
                row.seconds - median(history[key])
                for key, row in recent.items()
                if len(history[key]) >= 2
            ]
            if len(deltas) < 4:
                continue
            loss = median(deltas)
            if loss > max(1.0, 1.5 * (mad(deltas) or 0)):
                changes.append(
                    {"sector": number, "slowdown_s": loss, "drivers": len(deltas)}
                )
        return changes


def warmup_model(timing, archive, before_epoch):
    measured = timing.warmup_samples(max(0, timing.cutoff - 900_000))
    result = {}
    for tyre in FAMILIES:
        for sector in (2, 3):
            key = tyre, sector
            group = measured.get(key, [])
            scope = "current race"
            if len(group) < 3:
                group = [
                    row["warmup"][f"{tyre}:{sector}"]
                    for row in archive
                    if row["available_after"] < before_epoch
                    and f"{tyre}:{sector}" in row.get("warmup", {})
                ]
                scope = "earlier races"
            if len(group) >= (3 if scope == "current race" else 2):
                result[key] = {
                    "loss_s": max(0.0, median(group)),
                    "samples": len(group),
                    "scope": scope,
                }
    return result
