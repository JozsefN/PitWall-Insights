"""Lap-by-lap rival counterfactuals over supported plans and observed headways."""

from collections.abc import Callable
from dataclasses import dataclass, field

from .replay_plans import Curve, ranked_call


@dataclass
class DriverPlans:
    plans: list
    current: Curve
    curves: dict
    age: int
    completed: int
    remaining: int
    persistent_loss: float
    green_pit_s: float | None
    first_pit_cost: Callable[[int], float]
    sensitivity: float
    paths: dict = field(default_factory=dict)
    warmup_s: float = 0.0

    def path(self, plan):
        key = tuple((stop["lap"], stop["compound"]) for stop in plan["stops"])
        if key not in self.paths:
            changes = dict(key)
            result = []
            age, curve, loss = self.age, self.current, self.persistent_loss
            warmup = 0.0
            for offset in range(1, self.remaining + 1):
                age += 1
                pace = curve.base_s + curve.age_drift_s * age + loss + warmup
                warmup = 0.0
                fitted = changes.get(self.completed + offset)
                service = 0.0
                if fitted:
                    service = (
                        self.first_pit_cost(offset)
                        if offset == key[0][0] - self.completed
                        else self.green_pit_s
                    )
                    curve, age, loss = self.curves[fitted], 0, 0.0
                    warmup = self.warmup_s
                result.append((pace, service))
            self.paths[key] = result
        return self.paths[key]


def plan_action(plan, completed):
    first = plan["stops"][0] if plan["stops"] else None
    return (
        "finish"
        if first is None
        else "box" if first["lap"] == completed + 1 else "extend"
    )


def duel_path(own, rival, starting_gap, following_cost):
    """Positive gap means the rival is ahead. A crossover is a timing result."""
    gaps = []
    loss, gap = 0.0, starting_gap
    for (own_pace, own_stop), (rival_pace, rival_stop) in zip(own, rival):
        # Only add a measured following association when the rival is close enough to hold the car up.
        traffic = (
            min(following_cost, max(0, rival_pace - own_pace))
            if 0 < gap <= 1.2 and not own_stop and not rival_stop
            else 0.0
        )
        gap += own_pace + own_stop + traffic - rival_pace - rival_stop
        loss += traffic
        gaps.append(gap)
    return gaps, loss


def slow_stop_window(own_gap, pit_cost, slow_stop, pit_scatter):
    if own_gap is None or not slow_stop:
        return None
    actual_margin = -own_gap - pit_cost
    normal_margin = actual_margin - slow_stop["excess_s"]
    tolerance = max(pit_scatter or 0, slow_stop["scatter_s"], 0.15)
    if not actual_margin > tolerance or not normal_margin < -tolerance:
        return None
    return {**slow_stop, "margin_s": actual_margin, "normal_margin_s": normal_margin}


def duel_scenarios(own_id, rival_id, own_model, rival_model, race_gaps, following_cost):
    if (
        own_id not in race_gaps
        or rival_id not in race_gaps
        or own_model.remaining != rival_model.remaining
    ):
        return [], None
    own_gap, rival_gap = race_gaps[own_id], race_gaps[rival_id]
    peer_options = (
        (
            "holds",
            next(
                (
                    plan
                    for plan in rival_model.plans
                    if plan_action(plan, rival_model.completed) != "box"
                ),
                None,
            ),
        ),
        (
            "boxes",
            next(
                (
                    plan
                    for plan in rival_model.plans
                    if plan_action(plan, rival_model.completed) == "box"
                ),
                None,
            ),
        ),
        (
            "finishes",
            next((plan for plan in rival_model.plans if not plan["stops"]), None),
        ),
    )
    output, contextual_call = [], None
    for assumption, peer_plan in peer_options:
        if peer_plan is None:
            continue
        peer_path = rival_model.path(peer_plan)
        by_action, going = {}, []
        for plan in own_model.plans:
            own_path = own_model.path(plan)
            progress, traffic = duel_path(
                own_path, peer_path, own_gap - rival_gap, following_cost
            )
            if not progress:
                continue
            adjusted = plan["projected_time_s"] + traffic
            action = plan_action(plan, own_model.completed)
            going.append(
                {
                    **plan,
                    "projected_time_s": adjusted,
                    "green_time_s": plan["green_time_s"] + traffic,
                }
            )
            if action in by_action and by_action[action]["time_s"] <= adjusted:
                continue
            first = plan["stops"][0] if plan["stops"] else None
            relative_now = own_gap - rival_gap
            pass_lap = next(
                (
                    own_model.completed + index
                    for index, gap in enumerate(progress, 1)
                    if gap < 0
                    and (progress[index - 2] if index > 1 else relative_now) >= 0
                    and (first is None or own_model.completed + index >= first["lap"])
                ),
                None,
            )
            places_lost = None
            if action == "box":

                def rank(gap, rival_stop):
                    return 1 + sum(
                        value + (rival_stop if entry == rival_id else 0) < gap
                        for entry, value in race_gaps.items()
                        if entry != own_id
                    )

                places_lost = rank(own_gap + own_path[0][1], peer_path[0][1]) - rank(
                    own_gap, 0.0
                )
            pace_horizon = min(3, len(own_path) - 1)
            fresh_advantage = (
                sum(
                    rival_path_lap[0] - own_path_lap[0]
                    for own_path_lap, rival_path_lap in zip(
                        own_path[1 : pace_horizon + 1], peer_path[1 : pace_horizon + 1]
                    )
                )
                / pace_horizon
                if action == "box" and pace_horizon
                else None
            )
            by_action[action] = {
                "action": action,
                "first_stop": first,
                "finish_margin_s": -progress[-1],
                "crossover_lap": pass_lap,
                "positions_lost": places_lost,
                "post_pit_pace_advantage_s": fresh_advantage,
                "traffic_loss_s": traffic,
                "time_s": adjusted,
            }
        if not by_action:
            continue
        choices = sorted(by_action.values(), key=lambda row: row["time_s"])
        for row in choices:
            row["cost_vs_best_s"] = row["time_s"] - choices[0]["time_s"]
        output.append(
            {
                "assumption": assumption,
                "rival_first_stop": (
                    peer_plan["stops"][0] if peer_plan["stops"] else None
                ),
                "preferred_action": choices[0]["action"],
                "choices": choices,
            }
        )
        if (
            assumption == "holds"
            and following_cost > 0
            and any(row["traffic_loss_s"] > 0 for row in choices)
        ):
            ordered = sorted(
                going, key=lambda plan: (plan["projected_time_s"], len(plan["stops"]))
            )
            contextual_call = ranked_call(
                ordered, own_model.completed, own_model.sensitivity
            )
            contextual_call["rival_context_id"] = rival_id
    return output, contextual_call
