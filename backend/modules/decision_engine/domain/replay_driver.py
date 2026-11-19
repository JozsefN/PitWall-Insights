"""Build supported driver scenarios and rank pit calls."""

from dataclasses import dataclass
from functools import lru_cache
from math import ceil

from modules.feature_metrics.domain.analysis.models import AnalysisData
from modules.feature_metrics.domain.review.intervention import phase_at_pit
from modules.feature_metrics.domain.review.pace import SLICKS
from modules.feature_metrics.domain.review.replay_tyres import (
    MAX_COMPARABLE_PACE_FRACTION,
    driver_stint,
    relative_compounds,
)
from modules.feature_metrics.domain.strategy.pits import latest_pit_transitions

from .replay_plans import Curve, decision_spread, plans_to_finish, ranked_call
from .replay_matchup import DriverPlans


@dataclass(frozen=True)
class PlanningEvidence:
    data: AnalysisData
    cutoff: int
    remaining: int | None
    rules: dict
    profiles: dict
    offsets: dict
    pits: dict
    gaps: dict
    headways: dict
    phase: str | None
    cohort: list
    episode_age: float
    warnings: list
    forecast: dict | None = None
    pit_entry_closed: bool = False
    fresh_tyres_warmup_s: float = 0.0


def driver_plan(entry, lap, rows, evidence, blocked):
    cutoff, remaining, phase = evidence.cutoff, evidence.remaining, evidence.phase
    profiles, pits, gaps = evidence.profiles, evidence.pits, evidence.gaps
    compound, age = lap.get("compound"), lap.get("tyre_life")
    profile = profiles.get(compound)
    stint = (
        driver_stint(entry, evidence.data, cutoff, lap, profile, evidence.warnings)
        if profile
        else {}
    )
    limit = evidence.rules.get("maxTyreAge", 100)
    observed_age = min(profile["observed_age"], limit) if profile else None
    output = {
        "entry_id": entry.id,
        "completed_laps": lap.get("lap_number", 0),
        "compound": compound,
        "tyre_age": age,
        "observed_age_limit": observed_age,
        "supported_laps_left": (
            max(0, observed_age - age)
            if observed_age is not None and age is not None
            else None
        ),
        "gap_to_leader_s": gaps.get(entry.id),
        "gap_ahead_s": evidence.headways.get(entry.id),
        "stint": stint,
        "call": None,
    }
    entered, exited = latest_pit_transitions(entry, cutoff)
    if not blocked and entered > exited:
        blocked = "Pit stop in progress."
    if not blocked and exited > (lap.get("lap_end_time_ms") or 0):
        blocked = "Waiting for a completed lap on the new tyre set."
    if not blocked and compound not in SLICKS:
        blocked = (
            "Dry-tyre rules do not cover the observed wet-tyre stint."
            if rows
            else "Waiting for a completed lap with known tyres."
        )
    if not blocked and (profile is None or age is None or stint.get("pace_s") is None):
        blocked = "More comparable clean laps with known tyre ages are needed."
    if blocked:
        return {**output, "status": blocked}
    recent = stint["pace_s"]
    if cutoff - lap["lap_end_time_ms"] > max(120000, 2500 * recent) and phase == "1":
        return {**output, "status": "No recent completed lap for this driver."}
    used = {row.get("compound") for row in rows} & SLICKS
    sets = (
        len(
            {row["stint_number"] for row in rows if row.get("stint_number") is not None}
        )
        or 1
    )
    relative = relative_compounds(profiles, evidence.offsets, compound)
    trend = max(0, profile["drift_s_lap"])
    if trend > 0 and output["supported_laps_left"] is not None:
        one_percent = ceil(recent * 0.01 / trend)
        if one_percent <= output["supported_laps_left"]:
            stint["laps_to_one_percent_slower"] = one_percent
    loss = stint["persistent_loss_s_lap"]
    intercept = recent - trend * age - loss
    curves = [
        Curve(
            name,
            intercept + delta,
            max(0, model["drift_s_lap"]),
            min(model["observed_age"], limit),
            model["pace_scatter_s"] + scatter,
        )
        for name, (delta, scatter, _) in relative.items()
        if (model := profiles[name])
        and abs(delta) <= MAX_COMPARABLE_PACE_FRACTION * recent
        and intercept + delta > 10
    ]
    current = next((curve for curve in curves if curve.compound == compound), None)
    if current is None:
        return {**output, "status": "No supported pace curve for the current tyre."}
    green = pits["median_s"]
    new_lap = next(
        (
            row
            for row in reversed(entry.laps)
            if row["lap_number"] == lap["lap_number"] + 1
        ),
        {},
    )
    elapsed_lap = max(
        0,
        (cutoff - (new_lap.get("lap_start_time_ms") or lap["lap_end_time_ms"])) / 1000,
    )
    first_arrival = max(0, recent - elapsed_lap)

    @lru_cache(maxsize=None)
    def pit_weights(length):
        if evidence.pit_entry_closed:
            return {}, "historical_phase"
        if phase in ("4", "6") and length == 1:
            return {"sc" if phase == "4" else "vsc": 1.0}, "current_phase_held"
        delay = first_arrival + (length - 1) * recent
        return (
            phase_at_pit(
                evidence.cohort, evidence.episode_age, delay, evidence.forecast
            ),
            "historical_phase",
        )

    def pit_cost(length):
        weights, _ = pit_weights(length)
        return green - sum(
            weight * (pits["discount_s"][key] or 0) for key, weight in weights.items()
        )

    plans = plans_to_finish(
        current,
        int(age),
        curves,
        remaining,
        lap["lap_number"],
        used,
        sets,
        evidence.rules.get("minSets", 1),
        green,
        pit_cost,
        loss,
        earliest_first_stop=2 if evidence.pit_entry_closed else 1,
        allow_exit_at_observed_limit=age < limit,
        required_compounds=(
            1
            if any(row.get("compound") in ("INTERMEDIATE", "WET") for row in rows)
            else 2
        ),
        warmup_s=evidence.fresh_tyres_warmup_s,
    )
    for plan in plans:
        if plan["stops"]:
            weights, basis = pit_weights(plan["stops"][0]["lap"] - lap["lap_number"])
            if weights:
                plan["pit_phase"] = {
                    "basis": basis,
                    "sc_pct": weights.get("sc", 0) * 100,
                    "vsc_pct": weights.get("vsc", 0) * 100,
                }
    spread = decision_spread(curves, remaining, pits["robust_scatter_s"])
    call = ranked_call(plans, lap["lap_number"], spread)
    rejoin = None
    if (
        green is not None
        and entry.id in gaps
        and len(gaps) >= 3
        and not evidence.pit_entry_closed
    ):
        exit_gap = gaps[entry.id] + pit_cost(1)
        rejoin = {
            "position": 1
            + sum(value < exit_gap for key, value in gaps.items() if key != entry.id),
            "timed_drivers": len(gaps),
            "gap_to_leader_s": exit_gap,
        }
    return {
        **output,
        "call": call,
        "_plans": (
            DriverPlans(
                plans,
                current,
                {curve.compound: curve for curve in curves},
                int(age),
                lap["lap_number"],
                remaining,
                loss,
                green,
                pit_cost,
                spread,
                warmup_s=evidence.fresh_tyres_warmup_s,
            )
            if plans
            else None
        ),
        "rejoin_if_pit": rejoin,
        "status": (
            None
            if call
            else (
                "Pit entry closed. Waiting for race control to reopen it."
                if evidence.pit_entry_closed
                else (
                    "No route to the flag fits the supported tyre ages and compound rules."
                    if green is not None
                    else "Need a same-circuit green pit-loss benchmark from three comparable stops."
                )
            )
        ),
    }
