from datetime import datetime, timedelta, timezone
import numpy as np
from scipy.stats import beta

OUTCOMES = ("sc", "vsc", "red", "none")


def incident_risk(data, request, context, state, result):
    entry = None
    race_start = data.coverage.get("race_start_utc")
    start = datetime.fromisoformat(race_start) if race_start else None
    track = context.track if context else None
    rows = []
    elapsed = state.get("stop_duration_s", 0)
    stop_bin = "4_10" if elapsed < 10 else "10_30" if elapsed < 30 else "30_plus"
    if start is not None and start.tzinfo is not None and track:
        rows = [
            row
            for row in context.incident_history
            if row.observed_at_utc.tzinfo is not None
            and row.observed_at_utc + timedelta(seconds=row.horizon_s) < start
            and row.circuit_key == track.circuit_key
            and row.horizon_s == request.race_horizon_s
            and row.stopped == state["stopped"]
            and row.surface == state["surface"]
            and row.recovery_access == state["recovery_access"]
            and row.elapsed_stop_bin == stop_bin
        ]
    rows.sort(key=lambda row: row.observed_at_utc)
    result.put(
        "incident_risk_cohort_n", len(rows), entry, n=len(rows), status="observed"
    )
    from .common import phase_at

    active = (
        (state["stopped"] or state["collision"])
        and phase_at(data, request.as_of_ms) in ("1", "2")
        and not state["in_pit"]
        and state["state"] != "stale"
        and str(data.coverage.get("session_phase") or "").lower()
        not in ("finished", "finalised", "inactive", "aborted", "ends")
    )
    evidence = {
        "horizon_s": request.race_horizon_s,
        "cohort_n": len(rows),
        "prior": "Beta(1,1) occurrence; Dirichlet(1,1,1,1) highest response",
        "circuit_key": track.circuit_key if track else None,
        "state": {
            "stopped": state["stopped"],
            "surface": state["surface"],
            "recovery_access": state["recovery_access"],
            "elapsed_stop_bin": stop_bin,
        },
        "calibration_status": "empirical_cohort_not_externally_validated",
        "not_aggregate_next_lap_hazard": True,
        "incident_entry_id": state.get("entry_id"),
    }
    if active and len(rows) >= request.min_probability_cohort:
        from .models import Bounds

        distribution = {
            outcome: 100
            * (sum(row.outcome == outcome for row in rows) + 1)
            / (len(rows) + 4)
            for outcome in OUTCOMES
        }
        result.put(
            "incident_response_distribution_pct",
            distribution,
            entry,
            n=len(rows),
            status="estimated",
            support=evidence,
        )
        for outcome, key in zip(
            OUTCOMES,
            (
                "incident_sc_probability_pct",
                "incident_vsc_probability_pct",
                "incident_red_probability_pct",
                "incident_no_neutralisation_probability_pct",
            ),
        ):
            if outcome == "none":
                occurrences = [row.outcome == "none" for row in rows]
            elif outcome == "red":
                occurrences = [row.outcome == "red" for row in rows]
            elif outcome == "sc":
                occurrences = [
                    (
                        row.sc_occurred
                        if row.sc_occurred is not None
                        else (
                            True
                            if row.outcome == "sc"
                            else False if row.outcome in ("none", "vsc") else None
                        )
                    )
                    for row in rows
                ]
            else:
                occurrences = [
                    (
                        row.vsc_occurred
                        if row.vsc_occurred is not None
                        else (
                            True
                            if row.outcome == "vsc"
                            else False if row.outcome == "none" else None
                        )
                    )
                    for row in rows
                ]
            # Dropping unknown red/SC cases would bias occurrence risk downward.
            if any(value is None for value in occurrences):
                continue
            count = sum(occurrences)
            a = count + 1
            b = len(rows) - count + 1
            interval = beta.ppf([0.025, 0.975], a, b) * 100
            result.put(
                key,
                100 * a / (a + b),
                entry,
                n=len(rows),
                status="estimated",
                bounds=Bounds(
                    lower=float(interval[0]),
                    upper=float(interval[1]),
                    meaning="credible_interval_95",
                ),
                support=evidence,
                warnings=[
                    "Conditional historical-cohort estimate. Matching does not remove selection bias; occurrence probabilities overlap and need not sum to 100%."
                ],
            )
    counts = np.ones(4)
    errors = []
    for index, row in enumerate(rows):
        target = OUTCOMES.index(row.outcome)
        if index >= 10:
            probabilities = counts / np.sum(counts)
            actual = np.eye(4)[target]
            errors.append(float(np.sum((probabilities - actual) ** 2)))
        counts[target] += 1
    result.put(
        "incident_risk_brier",
        float(np.mean(errors)) if len(errors) >= 10 else None,
        entry,
        n=len(errors),
        status="estimated",
        warnings=[
            "Chronological prequential score within this supplied cohort; no claim of independently verified calibration."
        ],
    )
    return dict(
        evidence,
        active_incident=active,
        probability_available=result.get("incident_sc_probability_pct", None)
        is not None,
        response_distribution_available=result.get(
            "incident_response_distribution_pct", None
        )
        is not None,
    )
