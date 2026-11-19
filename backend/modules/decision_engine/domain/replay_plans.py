"""Lap-by-lap dry-race plans using cutoff-bounded observations and explicit rules."""

from dataclasses import dataclass
from functools import lru_cache
import math


@dataclass(frozen=True)
class Curve:
    compound: str
    base_s: float
    age_drift_s: float
    max_age: int
    lap_scatter_s: float

    def cost(self, age, laps):
        return self.base_s * laps + self.age_drift_s * (
            age * laps + laps * (laps + 1) / 2
        )


def plans_to_finish(
    current,
    age,
    alternatives,
    remaining,
    completed,
    used,
    sets,
    min_sets,
    green_pit_s,
    pit_cost,
    persistent_loss,
    max_stops=3,
    earliest_first_stop=1,
    allow_exit_at_observed_limit=False,
    required_compounds=2,
    warmup_s=0.0,
):
    """Least-cost continuation for each first stop lap and tyre compound.

    A green first-stop cost may be replaced by a timing-weighted cost. Every
    later stop uses the green benchmark. Remaining laps are whole-lap equivalents.
    """
    curves = {curve.compound: curve for curve in alternatives}
    bits = {
        name: 1 << index
        for index, name in enumerate(sorted({*curves, *used, current.compound}))
    }
    used_bits = sum(bits[name] for name in used)

    def legal(compounds, sets_used):
        return compounds.bit_count() >= required_compounds and sets_used >= min_sets

    @lru_cache(maxsize=None)
    def continuation(compound, left, compounds, sets_used, stops_left):
        curve = curves[compound]
        best = (
            (curve.cost(0, left), ())
            if left <= curve.max_age and legal(compounds, sets_used)
            else None
        )
        if stops_left == 0 or green_pit_s is None:
            return best
        for length in range(1, min(curve.max_age, left - 1) + 1):
            after = left - length
            for fitted in curves:
                tail = continuation(
                    fitted,
                    after,
                    compounds | bits[fitted],
                    min(min_sets, sets_used + 1),
                    stops_left - 1,
                )
                if tail is None:
                    continue
                total = curve.cost(0, length) + green_pit_s + warmup_s + tail[0]
                if best is None or total < best[0]:
                    best = total, ((completed + remaining - after, fitted), *tail[1])
        return best

    def active_cost(laps):
        return current.cost(age, laps) + persistent_loss * laps

    def output(total, unadjusted, stops, phase_discount=0.0):
        return {
            "projected_time_s": total,
            "green_time_s": unadjusted,
            "neutralisation_saving_s": phase_discount,
            "warmup_s": warmup_s * len(stops),
            "stops": [{"lap": lap, "compound": compound} for lap, compound in stops],
        }

    plans = []
    if age + remaining <= current.max_age and legal(used_bits, sets):
        total = active_cost(remaining)
        plans.append(output(total, total, ()))
    if green_pit_s is not None and max_stops > 0:
        supported_extension = current.max_age - age
        # The car already has to reach the next open pit entry on its current
        # set. Keep that option at the observed-age limit.
        reachable = (
            max(1, supported_extension)
            if earliest_first_stop == 1 and allow_exit_at_observed_limit
            else supported_extension
        )
        for length in range(earliest_first_stop, min(remaining - 1, reachable) + 1):
            first_pit_cost = pit_cost(length)
            saving = green_pit_s - first_pit_cost
            for compound in curves:
                tail = continuation(
                    compound,
                    remaining - length,
                    used_bits | bits[compound],
                    min(min_sets, sets + 1),
                    max_stops - 1,
                )
                if tail is not None:
                    total = active_cost(length) + first_pit_cost + warmup_s + tail[0]
                    plan = output(
                        total,
                        total + saving,
                        ((completed + length, compound), *tail[1]),
                        saving,
                    )
                    if length > supported_extension:
                        plan["exit_lap_beyond_observed_age"] = True
                    plans.append(plan)
    return sorted(
        plans, key=lambda plan: (plan["projected_time_s"], len(plan["stops"]))
    )


def ranked_call(plans, completed, uncertainty):
    if not plans:
        return None
    best = plans[0]
    first = best["stops"][0] if best["stops"] else None
    green_best = min(plans, key=lambda plan: plan["green_time_s"])

    # Compare a different immediate decision even when many stop-lap variants tie.
    def box_now(plan):
        return bool(plan["stops"] and plan["stops"][0]["lap"] == completed + 1)

    alternative = next(
        (plan for plan in plans[1:] if box_now(plan) != box_now(best)), None
    )
    if alternative is None and len(plans) > 1:
        alternative = plans[1]
    margin_s = (
        alternative["projected_time_s"] - best["projected_time_s"]
        if alternative
        else None
    )
    similar = [
        plan["stops"][0]["lap"]
        for plan in plans
        if plan["stops"]
        and first
        and plan["stops"][0]["compound"] == first["compound"]
        and plan["projected_time_s"] <= best["projected_time_s"] + uncertainty
    ]
    return {
        "action": "box" if box_now(best) else "extend" if first else "finish",
        "best": best,
        "alternative": alternative,
        "green_best": green_best,
        "candidate_count": len(plans),
        "margin_s": margin_s,
        "margin_pct": (
            100 * margin_s / alternative["projected_time_s"]
            if alternative and alternative["projected_time_s"] > 0
            else None
        ),
        "decision_sensitive": margin_s is not None and margin_s <= uncertainty,
        "sensitivity_s": uncertainty,
        "pit_window": [min(similar), max(similar)] if similar else None,
        "incident_changed_call": best["stops"] != green_best["stops"],
    }


def decision_spread(curves, remaining, pit_scatter):
    return math.hypot(
        (pit_scatter or 0),
        max(curve.lap_scatter_s for curve in curves) * math.sqrt(remaining),
    )
