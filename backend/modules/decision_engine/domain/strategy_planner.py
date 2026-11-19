"""Bounded exhaustive pit/tyre scenario search. No AI and no implicit tyre inventory."""

import heapq
from itertools import permutations
import numpy as np
from modules.feature_metrics.domain.strategy.models import (
    StrategyPlan,
    PlanStop,
    Bounds,
)
from modules.feature_metrics.domain.strategy.common import phase_at
from modules.feature_metrics.domain.strategy.pits import visits


def tyre_delta(curve, age, fit_lap):
    warmup = (
        curve.warmup_deltas_s[fit_lap - 1]
        if 0 < fit_lap <= len(curve.warmup_deltas_s)
        else 0
    )
    return (
        curve.base_delta_s
        + curve.degradation_s_per_lap * age
        + curve.quadratic_s_per_lap2 * age * age
        + warmup
    )


def plan_strategies(data, request, context, result, pit):
    session_phase = data.coverage.get("session_phase")
    if (
        request.mode == "race"
        and session_phase is not None
        and session_phase.lower()
        in ("finished", "finalised", "inactive", "aborted", "ends", "suspended")
    ):
        return (
            [],
            None,
            "session_not_running",
            {"session_phase": session_phase, "counterfactual_mode_required": True},
        )
    entry = request.focus_entry_id
    compound = result.get("strategy_current_compound", entry)
    age = result.get("strategy_reported_tyre_age_laps", entry)
    pace = result.get("strategy_recent_pace_s", entry)
    missing = []
    curves = {row.compound: row for row in context.tyre_curves} if context else {}
    inventory = context.tyre_inventory.get(entry, []) if context else []
    rules = context.rules if context else None
    for name, valid in (
        ("remaining_laps", request.remaining_laps is not None),
        ("current_tyre", compound in curves and age is not None),
        ("clean_pace", pace is not None),
        ("tyre_inventory", bool(inventory)),
        ("pit_loss", pit["loss"] is not None),
        ("rule_profile", rules is not None),
    ):
        if not valid:
            missing.append(name)
    if missing:
        return [], None, "missing_model_inputs", {"missing": missing}
    phase = phase_at(data, request.as_of_ms)
    initial_pit_loss = pit["loss"]
    if phase in ("4", "6", "7"):
        model = pit["model"]
        initial_pit_loss = (
            (model.sc_s if phase == "4" else model.vsc_s) if model else None
        )
    if phase not in ("1", "2", "4", "6", "7") or initial_pit_loss is None:
        return [], None, "unsupported_current_flag_phase", {"phase": phase}
    focus = next(row for row in data.entries if row.id == entry)
    completed = [
        row
        for row in focus.laps
        if row.get("lap_end_time_ms") is not None
        and row["lap_end_time_ms"] <= request.as_of_ms
    ]
    completed.sort(key=lambda row: row["lap_number"])
    latest_complete = completed[-1]["lap_end_time_ms"] if completed else -1
    latest_in = max(
        (
            row["pit_in_time_ms"]
            for row in focus.laps
            if row.get("pit_in_time_ms") is not None
        ),
        default=-1,
    )
    latest_out = max(
        (
            row["pit_out_time_ms"]
            for row in focus.laps
            if row.get("pit_out_time_ms") is not None
        ),
        default=-1,
    )
    if latest_in > latest_out or max(latest_in, latest_out) > latest_complete:
        return (
            [],
            None,
            "awaiting_observed_postpit_tyre_state",
            {
                "reason": "Do not charge an already-started stop twice or guess the currently fitted compound"
            },
        )
    fitted_laps = (
        sum(
            row.get("stint_number") == completed[-1].get("stint_number")
            for row in completed
        )
        if completed
        else age
    )
    count = request.remaining_laps
    current = curves[compound]
    used_compounds = {row.get("compound") for row in completed if row.get("compound")}
    prior_stops = len(visits(focus, request.as_of_ms))
    reference_base = pace - tyre_delta(current, age, fitted_laps)
    # Prefix costs let every stop combination be evaluated without simulating every lap again.
    assets = [
        dict(
            set_id="current",
            compound=compound,
            age=age + pit.get("decision_age_increment_laps", 0),
            fit_lap=fitted_laps,
        ),
        *[
            dict(
                set_id=row.set_id,
                compound=row.compound,
                age=row.initial_age_laps,
                fit_lap=0,
            )
            for row in inventory
            if row.compound in curves
        ],
    ]
    prefix = []
    errors = []
    for asset in assets:
        curve = curves[asset["compound"]]
        sequence = [
            (
                reference_base
                + tyre_delta(curve, asset["age"] + lap, asset["fit_lap"] + lap)
                if asset["age"] + lap <= curve.max_valid_age_laps
                else np.inf
            )
            for lap in range(1, count + 1)
        ]
        prefix.append(np.r_[0, np.cumsum(sequence)])
        errors.append(curve.uncertainty_s_per_lap)
    baseline = float(prefix[0][count]) if np.isfinite(prefix[0][count]) else None
    best = []
    first_stop_best = {}
    evaluated = 0
    legal = 0
    serial = 0
    assumptions = [
        "Conditional elapsed-time ranking, not guaranteed finishing position.",
        "Planning starts at the next reachable pit-entry decision boundary; partial-lap travel is common to alternatives.",
        "Future laps use the declared tyre curves and constant common base pace; no future fuel/weather/traffic/overtaking model is silently added.",
        "Only an immediate stop uses the current SC/VSC pit-cost input; later stops use green cost. Future neutralisation duration is unknown.",
        "Inventory and rules are supplied context, not automatically certified FIA eligibility.",
    ]

    def evaluate(stops):
        nonlocal evaluated, legal, serial
        evaluated += 1
        compounds = used_compounds | {assets[index]["compound"] for _, index in stops}
        if (
            len(compounds) < rules.minimum_distinct_compounds
            or prior_stops + len(stops) < rules.minimum_stops
        ):
            return
        total = 0.0
        error = 0.0
        previous = 0
        fitted = 0
        for offset, index in [*stops, (count, -1)]:
            segment = offset - previous
            value = float(prefix[fitted][segment])
            if not np.isfinite(value):
                return
            total += value
            error += errors[fitted] * segment
            if index >= 0:
                total += initial_pit_loss if offset == 0 else pit["loss"]
                error += pit["error"]
            previous = offset
            fitted = index
        legal += 1
        first = stops[0][0] if stops else None
        first_stop_best[first] = min(first_stop_best.get(first, float("inf")), total)
        serial += 1
        if len(best) >= 20 and total >= -best[0][0]:
            return
        plan = StrategyPlan(
            stops=[
                PlanStop(
                    after_laps=offset,
                    set_id=assets[index]["set_id"],
                    compound=assets[index]["compound"],
                )
                for offset, index in stops
            ],
            projected_time_s=round(total, 6),
            sensitivity=Bounds(
                lower=total - error, upper=total + error, meaning="sensitivity_range"
            ),
            gain_vs_stay_out_s=baseline - total if baseline is not None else None,
            satisfies_configured_rules=True,
            assumptions=assumptions,
        )
        item = (-total, -serial, plan)
        if len(best) < 20:
            heapq.heappush(best, item)
        elif total < -best[0][0]:
            heapq.heapreplace(best, item)

    evaluate([])
    if request.max_stops >= 1:
        for index in range(1, len(assets)):
            for offset in range(count):
                evaluate([(offset, index)])
    if request.max_stops >= 2:
        for first, second in permutations(range(1, len(assets)), 2):
            for a in range(count - 1):
                for b in range(a + 1, count):
                    evaluate([(a, first), (b, second)])
    plans = sorted(
        (row[2] for row in best),
        key=lambda row: (
            row.projected_time_s,
            [(stop.after_laps, stop.set_id) for stop in row.stops],
        ),
    )
    winner = plans[0] if plans else None
    result.put(
        "strategy_feasible_plan_count", legal, entry, n=evaluated, status="derived"
    )
    result.put(
        "strategy_best_gain_vs_stay_out_s",
        winner.gain_vs_stay_out_s if winner else None,
        entry,
        n=legal,
        status="assumed",
    )
    if winner:
        tolerance = max(1, (winner.sensitivity.upper - winner.sensitivity.lower) / 2)
        offsets = [
            offset
            for offset, value in first_stop_best.items()
            if offset is not None and value <= winner.projected_time_s + tolerance
        ]
        result.put(
            "strategy_first_stop_window_laps",
            (
                {
                    "earliest": min(offsets),
                    "latest": max(offsets),
                    "tolerance_s": tolerance,
                }
                if offsets
                else None
            ),
            entry,
            n=legal,
            status="assumed",
        )
    for rival in [
        row
        for row in data.entries
        if row.id != entry
        and (request.rival_entry_ids is None or row.id in request.rival_entry_ids)
    ]:
        gap = result.get("rival_projected_gap_s", entry, rival.id)
        rival_rows = [
            row
            for row in rival.laps
            if row.get("lap_end_time_ms") is not None
            and row["lap_end_time_ms"] <= request.as_of_ms
        ]
        rival_rows.sort(key=lambda row: row["lap_number"])
        last = rival_rows[-1] if rival_rows else {}
        rival_curve = curves.get(last.get("compound"))
        rival_age = last.get("tyre_life")
        horizons = []
        if gap is not None and gap > 0 and rival_curve and rival_age is not None:
            for index in range(1, len(assets)):
                curve = curves[assets[index]["compound"]]
                gain = 0.0
                for horizon in range(1, count + 1):
                    own_age = assets[index]["age"] + horizon
                    if (
                        own_age > curve.max_valid_age_laps
                        or rival_age + horizon > rival_curve.max_valid_age_laps
                    ):
                        break
                    gain += tyre_delta(
                        rival_curve, rival_age + horizon, rival_age + horizon
                    ) - tyre_delta(curve, own_age, horizon)
                    if gain > gap:
                        horizons.append(horizon)
                        break
        result.put(
            "pit_undercut_break_even_laps",
            min(horizons) if horizons else None,
            entry,
            rival.id,
            status="assumed",
            warnings=[
                "Tyre-only, common baseline assumption. Rival pit response, traffic, out-lap and in-lap execution are not observed future facts."
            ],
        )
    return (
        plans,
        winner,
        "conditional_model_ranking" if winner else "no_feasible_plan",
        dict(
            evaluated=evaluated,
            feasible=legal,
            scope="configured_zero_one_two_stop_plans",
            objective="minimum_modeled_elapsed_time",
            assumptions=assumptions,
        ),
    )
