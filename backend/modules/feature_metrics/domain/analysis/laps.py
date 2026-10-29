from collections import Counter, defaultdict
import numpy as np
from .common import numeric, stat, selected_laps, pit_windows


def calculate_laps(data, request, result):
    for entry in data.entries:
        all_laps = selected_laps(entry, data, request)
        clean = selected_laps(entry, data, request, clean=True)
        values = numeric(clean, "lap_time_ms")
        n = len(clean)

        def put(key, value):
            result.put(
                key,
                value,
                entry.id,
                n=n,
                confidence=min(1, n / 5),
                warnings=(
                    ["No fuel, weather or traffic correction is applied."]
                    if key
                    in (
                        "recent_pace_change_ms",
                        "theoretical_best_lap_ms",
                        "potential_sector_gain_ms",
                    )
                    else []
                ),
            )

        result.put("lap_count", len(all_laps), entry.id, n=len(all_laps))
        result.put("clean_lap_count", n, entry.id, n=len(all_laps))
        result.put(
            "deleted_lap_count",
            sum(bool(lap.get("is_deleted")) for lap in all_laps),
            entry.id,
            n=len(all_laps),
        )
        for key, operation in (
            ("best_lap_ms", "min"),
            ("median_lap_ms", "median"),
            ("mean_lap_ms", "mean"),
            ("lap_std_ms", "std"),
        ):
            put(key, stat(values, operation))
        median = stat(values, "median")
        mean = stat(values, "mean")
        deviation = stat(values, "std")
        put(
            "lap_mad_ms",
            stat(np.abs(values - median), "median") if median is not None else None,
        )
        put("lap_cv_pct", deviation / mean * 100 if mean else None)
        put("lap_p90_p10_ms", stat(values, "p90") - stat(values, "p10") if n else None)
        put("recent_pace_ms", stat(values[-5:], "median"))
        put(
            "recent_pace_change_ms",
            (
                stat(values[-5:], "median") - stat(values[-10:-5], "median")
                if n >= 6
                else None
            ),
        )
        put("last_lap_vs_best_ms", values[-1] - np.min(values) if n else None)
        best_sectors = []
        for sector in range(1, 4):
            sectors = numeric(clean, f"sector_{sector}_time_ms")
            sectors[sectors <= 0] = np.nan
            best_sectors.append(stat(sectors, "min"))
            for suffix, operation in (
                ("best", "min"),
                ("median", "median"),
                ("std", "std"),
            ):
                put(f"sector_{sector}_{suffix}_ms", stat(sectors, operation))
        theoretical = (
            sum(best_sectors)
            if all(value is not None for value in best_sectors)
            else None
        )
        put("theoretical_best_lap_ms", theoretical)
        put(
            "potential_sector_gain_ms",
            (
                max(0, float(np.min(values)) - theoretical)
                if n and theoretical is not None
                else None
            ),
        )
        mismatches = 0
        for lap in all_laps:
            sectors = [lap.get(f"sector_{sector}_time_ms") for sector in range(1, 4)]
            if (
                all(value is not None and value > 0 for value in sectors)
                and lap.get("lap_time_ms") is not None
            ):
                mismatches += abs(sum(sectors) - lap["lap_time_ms"]) > 100
        result.put(
            "sector_sum_mismatch_count", int(mismatches), entry.id, n=len(all_laps)
        )


def calculate_stints(data, request, result):
    for entry in data.entries:
        laps = selected_laps(entry, data, request)
        clean = selected_laps(entry, data, request, clean=True)
        by_stint = defaultdict(list)
        clean_stints = defaultdict(list)
        for lap in laps:
            if lap.get("stint_number") is not None:
                by_stint[lap["stint_number"]].append(lap)
        for lap in clean:
            if lap.get("stint_number") is not None:
                clean_stints[lap["stint_number"]].append(lap)

        def put(key, value, confidence=1):
            result.put(key, value, entry.id, n=len(laps), confidence=confidence)

        put("stint_count", len(by_stint))
        put(
            "longest_stint_laps",
            max((len(rows) for rows in by_stint.values()), default=0),
        )
        put(
            "compound_lap_counts",
            dict(Counter(lap.get("compound") or "UNKNOWN" for lap in laps)),
        )
        pace = []
        slopes = []
        baselines = {}
        for number, rows in sorted(clean_stints.items()):
            baseline = stat(numeric(rows, "lap_time_ms"), "median")
            baselines[number] = baseline
            pace.append(
                {
                    "stint": number,
                    "compound": rows[0].get("compound"),
                    "median_ms": baseline,
                    "clean_laps": len(rows),
                }
            )
            valid = [lap for lap in rows if lap.get("tyre_life") is not None]
            x = numeric(valid, "tyre_life")
            y = numeric(valid, "lap_time_ms")
            slope = (
                float(np.polyfit(x, y, 1)[0])
                if len(valid) >= 3 and np.ptp(x) > 0
                else None
            )
            slopes.append(
                {
                    "stint": number,
                    "slope_ms_per_lap": slope,
                    "samples": len(valid),
                    "confidence": min(0.6, len(valid) / 15),
                    "fuel_corrected": False,
                }
            )
        put("stint_pace", pace)
        put("tyre_degradation_ms_per_lap", slopes, 0.6)
        ins = {
            lap["pit_in_time_ms"]
            for lap in entry.laps
            if lap.get("pit_in_time_ms") is not None
            and data.start_ms <= lap["pit_in_time_ms"] <= data.end_ms
        }
        outs = {
            lap["pit_out_time_ms"]
            for lap in entry.laps
            if lap.get("pit_out_time_ms") is not None
            and data.start_ms <= lap["pit_out_time_ms"] <= data.end_ms
        }
        visits = [
            (end - start) / 1000
            for start, end in pit_windows(entry)
            if data.start_ms <= start < end <= data.end_ms
        ]
        put("pit_in_count", len(ins))
        put("pit_out_count", len(outs))
        put("pit_visit_durations_s", visits)
        put("mean_pit_visit_s", stat(visits, "mean"))
        put("best_pit_visit_s", stat(visits, "min"))
        put(
            "out_lap_delta_ms",
            [
                {
                    "lap": lap["lap_number"],
                    "delta_ms": lap["lap_time_ms"] - baselines[lap["stint_number"]],
                }
                for lap in laps
                if lap.get("pit_out_time_ms") is not None
                and lap.get("lap_time_ms") is not None
                and baselines.get(lap.get("stint_number")) is not None
            ],
            0.6,
        )
