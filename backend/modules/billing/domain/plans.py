from dataclasses import dataclass
from typing import Literal

PlanCode = Literal["free", "analyst", "pro"]
PaidPlan = Literal["analyst", "pro"]
Interval = Literal["month", "year"]


@dataclass(frozen=True)
class Plan:
    code: PlanCode
    name: str
    level: int
    saved_layouts: int
    panels_per_layout: int
    ai_monthly_planned: int | None  # None denotes unlimited access when AI launches.
    ai_features_planned: tuple[str, ...]
    prices_huf: dict[str, int]


ANALYST_AI = ("session_summary", "driver_comparison")
PLANS = {
    "free": Plan("free", "Free", 0, 2, 4, 0, (), {}),
    "analyst": Plan("analyst", "Analyst", 1, 10, 10, 500, ANALYST_AI, {"month": 1490, "year": 14900}),
    "pro": Plan("pro", "Pro", 2, 30, 20, None, (*ANALYST_AI, "session_questions", "replay_lap_summary"),
                {"month": 2490, "year": 24900}),
}
FREE = PLANS["free"]
ANALYST = PLANS["analyst"]


class EntitlementError(Exception):
    pass
