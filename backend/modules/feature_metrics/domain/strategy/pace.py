import numpy as np
from scipy.stats import t
from .common import clean_laps, mad, slope, band


def pace_features(data, request, result):
    entry = next(row for row in data.entries if row.id == request.focus_entry_id)
    clean = clean_laps(entry, request.as_of_ms)
    recent = clean[-10:]
    times = np.array([row["lap_time_ms"] / 1000 for row in recent])
    result.put(
        "strategy_clean_laps", len(clean), entry.id, n=len(clean), status="observed"
    )
    result.put(
        "strategy_recent_pace_s",
        float(np.median(times[-5:])) if len(times) else None,
        entry.id,
        n=len(times[-5:]),
        status="estimated",
    )
    result.put(
        "strategy_pace_scatter_s",
        mad(times),
        entry.id,
        n=len(times),
        status="estimated",
    )
    result.put(
        "strategy_pace_trend_s_per_lap",
        slope([row["lap_number"] for row in recent], times),
        entry.id,
        n=len(times),
        status="estimated",
    )
    result.put(
        "strategy_last_lap_residual_s",
        float(times[-1] - np.median(times[-6:-1])) if len(times) > 1 else None,
        entry.id,
        n=len(times),
        status="estimated",
    )
    completed = sorted(
        [
            row
            for row in entry.laps
            if row.get("lap_end_time_ms") is not None
            and row["lap_end_time_ms"] <= request.as_of_ms
        ],
        key=lambda row: row["lap_number"],
    )
    last = completed[-1] if completed else {}
    result.put(
        "strategy_current_compound",
        last.get("compound"),
        entry.id,
        status="observed",
        n=1 if last else 0,
    )
    result.put(
        "strategy_reported_tyre_age_laps",
        last.get("tyre_life"),
        entry.id,
        status="observed",
        n=1 if last else 0,
    )
    return fit_pace(data, request, result)


def fit_pace(data, request, result):
    rows = [
        dict(row, entry_id=entry.id)
        for entry in data.entries
        for row in clean_laps(entry, request.as_of_ms)
        if row.get("tyre_life") is not None and row.get("compound")
    ]
    if len(rows) < 12:
        return {
            "status": "insufficient_data",
            "rows": len(rows),
            "required_minimum": 12,
        }
    drivers = sorted({row["entry_id"] for row in rows})
    compounds = sorted({row["compound"] for row in rows})
    names = (
        ["intercept"]
        + ["driver:" + driver for driver in drivers[1:]]
        + ["compound:" + compound for compound in compounds[1:]]
    )
    names += ["age:" + compound for compound in compounds] + ["common_race_lap"]
    matrix = []
    for row in rows:
        matrix.append(
            [1]
            + [float(row["entry_id"] == driver) for driver in drivers[1:]]
            + [float(row["compound"] == compound) for compound in compounds[1:]]
            + [
                float(row["tyre_life"]) if row["compound"] == compound else 0
                for compound in compounds
            ]
            + [row["lap_number"]]
        )
    x = np.asarray(matrix, dtype=float)
    y = np.array([row["lap_time_ms"] / 1000 for row in rows])
    scales = np.std(x, axis=0)
    scales[0] = 1
    if np.any(scales[1:] < 1e-9):
        return {
            "status": "unidentifiable",
            "reason": "Constant required predictor",
            "columns": names,
            "rows": len(rows),
        }
    normalized = x / scales
    singular = np.linalg.svd(normalized, compute_uv=False)
    condition = float(singular[0] / max(singular[-1], 1e-15))
    result.put(
        "strategy_pace_design_condition",
        condition,
        request.focus_entry_id,
        n=len(rows),
        status="derived",
    )
    if (
        np.linalg.matrix_rank(normalized) < x.shape[1]
        or condition > 1e8
        or len(rows) <= x.shape[1] + 5
    ):
        return {
            "status": "unidentifiable",
            "reason": "Tyre age and race lap/fuel/evolution cannot be separated in this design",
            "condition_number": condition,
            "columns": names,
            "rows": len(rows),
        }
    beta = np.linalg.lstsq(normalized, y, rcond=None)[0] / scales
    residual = y - x @ beta
    degrees = len(rows) - x.shape[1]
    variance = float(np.sum(residual**2) / degrees)
    covariance = (
        variance
        * np.linalg.inv(normalized.T @ normalized)
        / scales[:, None]
        / scales[None, :]
    )
    error = np.sqrt(np.maximum(0, np.diag(covariance))) * t.ppf(0.975, degrees)
    coefficients = {name: float(value) for name, value in zip(names, beta)}
    compound_rows = []
    for compound in compounds:
        index = names.index("age:" + compound)
        ages = [row["tyre_life"] for row in rows if row["compound"] == compound]
        compound_rows.append(
            dict(
                compound=compound,
                slope_s_per_lap=float(beta[index]),
                lower_95=float(beta[index] - error[index]),
                upper_95=float(beta[index] + error[index]),
                sample_count=len(ages),
                observed_age_min=min(ages),
                observed_age_max=max(ages),
            )
        )
    index = names.index("common_race_lap")
    result.put(
        "strategy_common_lap_trend_s_per_lap",
        beta[index],
        request.focus_entry_id,
        n=len(rows),
        status="estimated",
        bounds=band(beta[index], error[index], "coefficient_interval_95"),
        warnings=[
            "Common race-lap trend combines fuel, evolution and omitted conditions; it is not identified fuel burn."
        ],
    )
    result.put(
        "strategy_compound_age_slopes",
        compound_rows,
        request.focus_entry_id,
        n=len(rows),
        status="estimated",
        warnings=[
            "OLS intervals assume independent constant-variance residuals; serial correlation and weather can widen real uncertainty. Do not extrapolate beyond observed ages."
        ],
    )
    return {
        "status": "identifiable_observational_fit",
        "rows": len(rows),
        "columns": names,
        "condition_number": condition,
        "coefficients": coefficients,
        "residual_rmse_s": float(np.sqrt(variance)),
        "fuel_causally_identified": False,
        "weather_causally_corrected": False,
        "automatically_used_for_future_tyre_curves": False,
    }
