"""Robust tyre age and pace inputs for dry-race strategy scenarios."""

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations, groupby
from statistics import median

from ..strategy.common import clean_laps, mad, slope
from .pace import SLICKS, rain_state

# Larger separations between dry-compound runs indicate unmatched conditions.
# Reject the comparison instead of inventing a compound offset at the limit.
MAX_COMPARABLE_PACE_FRACTION = 0.03


@dataclass(frozen=True)
class StintFit:
    driver: str
    session_id: str
    source: str
    compound: str
    age_min: int
    age_max: int
    count: int
    trend: float
    intercept: float
    scatter: float
    endpoint_pct: float


def clean_tyre_laps(entry, data, cutoff):
    return [
        lap
        for lap in clean_laps(entry, cutoff)
        if lap.get("compound") in SLICKS
        and lap.get("stint_number") is not None
        and lap.get("tyre_life") is not None
        and 1 <= lap["tyre_life"] <= 100
        and rain_state(data, lap["lap_end_time_ms"]) is False
    ]


def _fit(driver, session_id, source, compound, laps):
    points = [
        (int(lap["tyre_life"]), lap["lap_time_ms"] / 1000)
        for lap in laps
        if lap["tyre_life"] >= 3
    ]
    if len(points) < 5:
        return None
    ages, times = zip(*points)
    trend = slope(ages, times)
    if trend is None:
        return None
    intercept = median(time - trend * age for age, time in points)
    scatter = mad([time - (intercept + trend * age) for age, time in points])
    core = [
        (age, time)
        for age, time in points
        if abs(time - intercept - trend * age) <= max(1.5, 3 * scatter)
    ]
    if len(core) < 5:
        return None
    ages, times = zip(*core)
    trend = slope(ages, times)
    if trend is None:
        return None
    intercept = median(time - trend * age for age, time in core)
    scatter = mad([time - (intercept + trend * age) for age, time in core])
    first, last = median(times[:2]), median(times[-2:])
    return StintFit(
        driver,
        session_id,
        source,
        compound,
        min(ages),
        max(ages),
        len(core),
        trend,
        intercept,
        scatter,
        100 * (last - first) / first,
    )


def stint_fits(data, cutoff, source):
    fits = []
    for entry in data.entries:
        for (_, compound), laps in groupby(
            clean_tyre_laps(entry, data, cutoff),
            lambda row: (row["stint_number"], row["compound"]),
        ):
            for _, run in groupby(
                enumerate(laps),
                lambda pair: (
                    pair[1]["lap_number"] - pair[0],
                    pair[1]["tyre_life"] - pair[0],
                ),
            ):
                fit = _fit(
                    entry.car_number,
                    data.session_id,
                    source,
                    compound,
                    [lap for _, lap in run],
                )
                if fit:
                    fits.append(fit)
    return fits


def compound_profiles(fits):
    profiles = {}
    for compound in sorted(SLICKS):
        rows = [fit for fit in fits if fit.compound == compound]
        if len(rows) < 2:
            continue
        practice = [fit for fit in rows if fit.source == "practice"]
        trends = [fit.trend for fit in rows]
        profiles[compound] = {
            "runs": len(rows),
            "practice_runs": len(practice),
            "previous_race_runs": sum(fit.source == "previous_race" for fit in rows),
            "current_race_runs": sum(fit.source == "current_race" for fit in rows),
            "observed_age": max(fit.age_max for fit in rows),
            "drift_s_lap": median(trends),
            "slope_scatter": mad(trends),
            "pace_scatter_s": median(fit.scatter for fit in rows),
            "practice_change_pct": (
                median(fit.endpoint_pct for fit in practice) if practice else None
            ),
        }
    return profiles


def compound_offsets(fits):
    """Pair compounds within a driver/session and inside their shared age range."""
    by_driver_session = defaultdict(list)
    for fit in fits:
        by_driver_session[(fit.driver, fit.session_id)].append(fit)
    pooled = defaultdict(list)
    for runs in by_driver_session.values():
        pairs = defaultdict(list)
        for one, two in combinations(sorted(runs, key=lambda model: model.compound), 2):
            age_min, age_max = max(one.age_min, two.age_min), min(
                one.age_max, two.age_max, 12
            )
            if one.compound == two.compound or age_min > age_max:
                continue
            reference_age = (age_min + age_max) / 2
            pace_one = one.intercept + one.trend * reference_age
            pace_two = two.intercept + two.trend * reference_age
            offset = two.intercept - one.intercept
            bound = MAX_COMPARABLE_PACE_FRACTION * min(pace_one, pace_two)
            if max(abs(pace_two - pace_one), abs(offset)) <= bound:
                pairs[(one.compound, two.compound)].append(offset)
        for key, values in pairs.items():
            pooled[key].append(median(values))
    return {
        key: (median(values), mad(values), len(values))
        for key, values in pooled.items()
        if len(values) >= 2
    }


def relative_compounds(profiles, offsets, current):
    if current not in profiles:
        return {}
    output = {current: (0.0, 0.0, 0)}
    links = {}
    for (one, two), (delta, scatter, count) in offsets.items():
        links[one, two] = delta, scatter, count
        links[two, one] = -delta, scatter, count
    for compound in profiles.keys() - {current}:
        if (current, compound) in links:
            output[compound] = links[current, compound]
            continue
        for intermediate in profiles.keys() - {current, compound}:
            if (current, intermediate) in links and (intermediate, compound) in links:
                a, b = links[current, intermediate], links[intermediate, compound]
                output[compound] = (a[0] + b[0], a[1] + b[1], min(a[2], b[2]))
    return output


def driver_stint(entry, data, cutoff, lap, profile, warnings):
    clean = [
        row
        for row in clean_tyre_laps(entry, data, cutoff)
        if row["stint_number"] == lap.get("stint_number")
        and row["compound"] == lap.get("compound")
    ]
    times = [row["lap_time_ms"] / 1000 for row in clean]
    base = median(times[-3:]) if times else None
    trend = max(0.0, profile["drift_s_lap"])
    level = [time - trend * row["tyre_life"] for row, time in zip(clean, times)]
    change_pct = None
    residual = 0.0
    if len(times) >= 5:
        first, last = median(times[:2]), median(times[-2:])
        change_pct = 100 * (last - first) / first
        early = median(level[:-2])
        recent = [value - early for value in level[-2:]]
        scatter = mad(level[:-2]) or 0
        if min(recent) > max(0.25, 2 * scatter):
            residual = median(recent)
    contact = (
        next(
            (
                row
                for row in warnings
                if row["kind"] in ("contact", "contact_mentioned")
                and entry.id in row["entry_ids"]
                and clean
                and clean[0]["lap_end_time_ms"]
                < row["time_ms"]
                <= clean[-2]["lap_end_time_ms"]
            ),
            None,
        )
        if len(clean) >= 5
        else None
    )
    return {
        "pace_s": base,
        "clean_laps": len(clean),
        "current_change_pct": change_pct,
        "persistent_loss_s_lap": residual,
        "loss_after_warning": contact["kind"] if contact and residual else None,
        "braking_evidence_laps": (
            [row["id"] for row in clean[-3:-1] if row.get("id")]
            if residual and not contact
            else []
        ),
    }
