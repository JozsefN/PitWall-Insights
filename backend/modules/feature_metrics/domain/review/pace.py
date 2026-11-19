"""Reusable clean-lap baselines and conditional race forecasts."""

from collections import defaultdict
from itertools import groupby
from statistics import median

from ..race_estimation.common import at, number
from ..strategy.common import clean_laps, mad, slope

SLICKS = {"SOFT", "MEDIUM", "HARD"}


def rain_state(data, stamp):
    row = at(data.weather, stamp, 120000)
    value = row.get("rainfall") if row else None
    return bool(value) if value in (0, 1, False, True) else None


def consecutive_stints(data, cutoff, fuel_gain_s=0):
    """Exclude short runs, pit laps and incomplete/discontinuous samples."""
    result = []
    for entry in data.entries:
        eligible = [
            lap
            for lap in clean_laps(entry, cutoff)
            if lap.get("stint_number") is not None and lap.get("compound") in SLICKS
        ]
        for (stint, compound), group in groupby(
            eligible, lambda lap: (lap["stint_number"], lap["compound"])
        ):
            for _, run in groupby(
                enumerate(group), lambda item: item[1]["lap_number"] - item[0]
            ):
                laps = [lap for _, lap in run]
                if len(laps) < 5:
                    continue
                times = [lap["lap_time_ms"] / 1000 for lap in laps]
                centre = median(times)
                scatter = mad(times) or 0
                kept = [
                    (lap, time)
                    for lap, time in zip(laps, times)
                    if abs(time - centre) <= max(2.5, 3 * scatter)
                ]
                if len(kept) < 5:
                    continue
                stamps = [lap["lap_number"] for lap, _ in kept]
                values = [time for _, time in kept]
                trend = slope(stamps, values)
                rain_flags = {
                    rain_state(data, item["lap_end_time_ms"]) for item, _ in kept
                }
                result.append(
                    {
                        "entry_id": entry.id,
                        "compound": compound,
                        "stint": stint,
                        "laps": stamps,
                        "median_pace_s": median(values),
                        "pace_scatter_s": mad(values),
                        "observed_trend_s_per_lap": trend,
                        "fuel_scenario_trend_s_per_lap": (
                            trend + fuel_gain_s
                            if trend is not None and fuel_gain_s
                            else None
                        ),
                        "rain_reported": (
                            next(iter(rain_flags)) if len(rain_flags) == 1 else None
                        ),
                        "tyre_age_min": number(kept[0][0].get("tyre_life")),
                        "tyre_age_max": number(kept[-1][0].get("tyre_life")),
                    }
                )
    return result


def practice_profiles(sessions, fuel_gain_s):
    grouped = defaultdict(list)
    for data in sessions:
        for row in consecutive_stints(data, data.end_ms, fuel_gain_s):
            if row["rain_reported"] is False:
                grouped[row["compound"]].append({**row, "session_id": data.session_id})
    return [
        {
            "compound": compound,
            "runs": len(rows),
            "laps": sum(len(row["laps"]) for row in rows),
            "median_observed_trend_s_per_lap": median(
                row["observed_trend_s_per_lap"] for row in rows
            ),
            "longest_observed_clean_run_laps": max(len(row["laps"]) for row in rows),
            "session_ids": sorted({row["session_id"] for row in rows}),
            "observations": rows[:30],
        }
        for compound, rows in sorted(grouped.items())
    ]


def pace_baselines(data, cutoff, intervals, fuel_gain_s):
    # The gap is sampled independently of the lap result. Unknown-gap laps remain
    # eligible for general pace, and are excluded from the traffic comparison.
    by_car = defaultdict(list)
    for row in intervals:
        by_car[row["driver_number"]].append(row)
    result = []
    for entry in data.entries:
        laps = clean_laps(entry, cutoff)
        if not laps:
            continue
        latest = laps[-1]
        same = [
            lap
            for lap in laps
            if lap.get("stint_number") == latest.get("stint_number")
            and lap.get("compound") == latest.get("compound")
        ][-8:]
        values = [lap["lap_time_ms"] / 1000 for lap in same]
        traffic, clear = [], []
        reports = by_car[entry.car_number]
        for lap in same:
            start, end = lap.get("lap_start_time_ms"), lap["lap_end_time_ms"]
            if start is None:
                continue
            observations = [
                (row["session_time_ms"], number(row.get("interval")))
                for row in reports
                if start <= row["session_time_ms"] <= end
            ]
            valid = [
                (stamp, gap)
                for stamp, gap in observations
                if gap is not None and gap > 0
            ]
            if len(valid) < max(5, (end - start) / 8000):
                continue
            fraction = sum(gap <= 1.2 for _, gap in valid) / len(valid)
            if fraction >= 0.5:
                traffic.append(lap["lap_time_ms"] / 1000)
            elif fraction <= 0.1:
                clear.append(lap["lap_time_ms"] / 1000)
        trend = (
            slope([lap["lap_number"] for lap in same], values)
            if len(same) >= 4
            else None
        )
        result.append(
            {
                "entry_id": entry.id,
                "lap_number": latest["lap_number"],
                "compound": latest.get("compound"),
                "tyre_age_laps": latest.get("tyre_life"),
                "samples": len(same),
                "median_pace_s": median(values[-5:]),
                "faster_observed_pace_s": sorted(values)[
                    max(0, (len(values) - 1) // 4)
                ],
                "traffic_pace_s": median(traffic) if len(traffic) >= 2 else None,
                "clear_pace_s": median(clear) if len(clear) >= 2 else None,
                "traffic_samples": len(traffic),
                "clear_samples": len(clear),
                "pace_scatter_s": mad(values),
                "observed_trend_s_per_lap": trend,
                "fuel_scenario_trend_s_per_lap": (
                    trend + fuel_gain_s if fuel_gain_s and trend is not None else None
                ),
                "last_lap_loss_s": (
                    values[-1] - median(values[:-1]) if len(values) >= 4 else None
                ),
            }
        )
    return result


def track_evolution(data, cutoff):
    """Compare repeated driver/compound/age observations at similar reported weather."""
    changes = []
    for entry in data.entries:
        groups = defaultdict(list)
        for lap in clean_laps(entry, cutoff):
            age = number(lap.get("tyre_life"))
            stamp = lap["lap_end_time_ms"]
            weather = at(data.weather, stamp, 120000)
            temp = number(weather.get("track_temp_c")) if weather else None
            if (
                age is not None
                and temp is not None
                and lap.get("compound") in SLICKS
                and rain_state(data, stamp) is False
            ):
                groups[(lap["compound"], round(age / 2), round(temp / 3))].append(lap)
        per_driver = []
        for rows in groups.values():
            first, last = rows[0], rows[-1]
            minutes = (last["lap_end_time_ms"] - first["lap_end_time_ms"]) / 60000
            if minutes >= 5:
                per_driver.append(
                    (last["lap_time_ms"] - first["lap_time_ms"]) / 1000 / minutes
                )
        if per_driver:
            changes.append(median(per_driver))
    return {
        "matched_drivers": len(changes),
        "pace_change_s_per_min": median(changes) if len(changes) >= 3 else None,
        "method": "Same driver, compound, tyre-age bucket and dry track-temperature bucket. Fuel, effort, traffic and rubber remain confounded.",
    }


def field_projection(
    pace, gaps, ranks, driver_ids, cutoff, horizon, green, fuel_gain_s=0
):
    if not green:
        return []
    by_entry = {row["entry_id"]: row for row in pace if row["samples"] >= 3}
    leader = next(
        (
            car
            for car in driver_ids
            if ranks.at(car, cutoff) and ranks.at(car, cutoff).get("position") == 1
        ),
        None,
    )
    leader_pace = by_entry.get(driver_ids.get(leader))
    if leader_pace is None:
        return []
    output = []
    for car, entry in driver_ids.items():
        row = by_entry.get(entry)
        if row is None:
            continue
        interval = gaps.at(car, cutoff)
        if car == leader:
            gap, lapped = 0, 0
        elif interval and cutoff - interval["session_time_ms"] <= 9000:
            raw = interval.get("gap_to_leader")
            gap = number(raw)
            lapped = (
                int(raw.split()[0].strip("+"))
                if isinstance(raw, str)
                and raw.endswith((" LAP", " LAPS"))
                and raw.split()[0].strip("+").isdigit()
                else 0
            )
            if lapped:
                output.append(
                    {
                        "entry_id": entry,
                        "laps_down_reported": lapped,
                        "projected_elapsed_s": None,
                        "reason": "Fractional timing gap inside the lap is unavailable.",
                    }
                )
                continue
        else:
            continue
        if gap is None or gap < 0:
            continue
        fuel_gain = fuel_gain_s * horizon * (horizon + 1) / 2
        estimate = gap + row["median_pace_s"] * horizon - fuel_gain
        spread = max(0.3, row["pace_scatter_s"] or 0) * horizon
        output.append(
            {
                "entry_id": entry,
                "laps_down_reported": lapped,
                "current_gap_to_leader_s": gap,
                "projected_elapsed_s": estimate,
                "sensitivity_s": [estimate - spread, estimate + spread],
                "assumed_fuel_gain_s": fuel_gain or None,
            }
        )
    ordered = sorted(
        (row for row in output if row["projected_elapsed_s"] is not None),
        key=lambda row: row["projected_elapsed_s"],
    )
    for index, row in enumerate(ordered, 1):
        row["order_among_projected_entries"] = index
        row["projected_gap_s"] = (
            row["projected_elapsed_s"] - ordered[0]["projected_elapsed_s"]
        )
    return [*ordered, *(row for row in output if row["projected_elapsed_s"] is None)]
