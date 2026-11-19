import unittest
from itertools import combinations, product

from modules.decision_engine.domain.replay_plans import (
    Curve,
    plans_to_finish,
    ranked_call,
)
from modules.feature_metrics.domain.analysis.models import AnalysisData, EntryData
from modules.feature_metrics.domain.race_estimation.braking import first_braking_plateau
from modules.feature_metrics.domain.review.intervention import (
    matched_cohort,
    phase_at_pit,
    probability_forecast,
    race_episodes,
)
from modules.feature_metrics.domain.review.replay_tyres import (
    compound_profiles,
    driver_stint,
    stint_fits,
)
from modules.feature_metrics.domain.review.replay_warnings import _vehicle_warning


def cohort_case(number, *, outcome=None, response=None, restart=None, available=100):
    return {
        "race": number,
        "circuit": 63,
        "available_after": available,
        "signals": [[0, "yellow"]],
        "outcome": outcome,
        "response_s": response,
        "restart_s": restart,
        "clear_s": None,
        "coverage_s": 300,
    }


class ReplayStrategyTests(unittest.TestCase):
    def test_causal_grouping_and_retrospective_notifications(self):
        def report(time_ms, message, flag=None, scope=None):
            return {
                "session_time_ms": time_ms,
                "message": message,
                "flag": flag,
                "scope": scope,
            }

        rows = [
            report(1000, "CAR 1 OFF TRACK AND CONTINUED"),
            report(5000, "YELLOW", "YELLOW", "Sector"),
            report(6000, "CAR 1 INCIDENT NOTED - CAUSING A COLLISION"),
            report(10000, "VIRTUAL SAFETY CAR DEPLOYED"),
            report(12000, "DOUBLE YELLOW", "DOUBLE YELLOW", "Sector"),
            report(34000, "GREEN FLAG", "GREEN", "Track"),
        ]
        causal = race_episodes(rows[:3], 0)
        self.assertIsNone(causal[0].outcome)
        self.assertEqual(causal[0].signals, [(1000, "off_track"), (5000, "yellow")])
        finished = race_episodes(rows, 0)
        self.assertEqual(len(finished), 1)
        self.assertEqual(
            (finished[0].outcome, finished[0].response_ms, finished[0].restart_ms),
            ("vsc", 10000, 34000),
        )

    def test_probabilities_exclude_future_early_resolved_and_right_censored_examples(
        self,
    ):
        rows = [
            cohort_case(index, outcome="sc", response=30, restart=180)
            for index in range(10)
        ]
        rows.extend(cohort_case(index) for index in range(10, 20))
        rows.extend(
            [
                cohort_case(21, outcome="sc", response=4, restart=180),
                cohort_case(22, available=200),
            ]
        )
        rows.append({**cohort_case(23), "coverage_s": 60})
        cohort, scope = matched_cohort(rows, "yellow", 10, 200, 63)
        forecast = probability_forecast(cohort, 10, scope)
        self.assertEqual(len(cohort), 20)
        self.assertAlmostEqual(sum(forecast["outcomes_pct"].values()), 100)
        self.assertAlmostEqual(forecast["outcomes_pct"]["sc"], 100 * 10.5 / 22)
        self.assertEqual(phase_at_pit(cohort, 10, 50), {"sc": 0.5, "vsc": 0})
        self.assertEqual(phase_at_pit(cohort, 10, 121), {})
        self.assertIsNone(probability_forecast(cohort[:4], 10, scope))

    def test_weighted_discount_can_change_the_first_stop(self):
        medium = Curve("MEDIUM", 80, 0.4, 25, 0.1)
        hard = Curve("HARD", 81, 0.0, 20, 0.1)
        args = (medium, 10, [hard], 5, 10, {"MEDIUM"}, 1, 1, 5.0)
        green = ranked_call(plans_to_finish(*args, lambda _: 5.0, 0), 10, 0.25)
        weighted = ranked_call(
            plans_to_finish(*args, lambda n: 5.0 - 0.5 * 8 if n == 2 else 5.0, 0),
            10,
            0.25,
        )
        self.assertEqual(green["best"]["stops"][0]["lap"], 11)
        self.assertEqual(weighted["best"]["stops"][0]["lap"], 12)
        self.assertTrue(weighted["incident_changed_call"])
        self.assertAlmostEqual(weighted["best"]["neutralisation_saving_s"], 4)

    def test_dynamic_search_agrees_with_independent_lap_by_lap_search(self):
        medium = Curve("MEDIUM", 80, 0.3, 8, 0.3)
        hard = Curve("HARD", 81, 0.1, 5, 0.2)
        rows = plans_to_finish(
            medium, 2, [medium, hard], 7, 20, {"MEDIUM"}, 1, 1, 3, lambda _: 3, 0.1, 2
        )
        totals = []
        for stop_count in (1, 2):
            for stops in combinations(range(1, 7), stop_count):
                for fitted in product([medium, hard], repeat=stop_count):
                    if hard not in fitted:
                        continue
                    length = [
                        last - first for first, last in zip((0, *stops), (*stops, 7))
                    ]
                    if length[0] + 2 > medium.max_age or any(
                        n > c.max_age for n, c in zip(length[1:], fitted)
                    ):
                        continue
                    total = 3 * stop_count + sum(
                        80 + 0.3 * age + 0.1 for age in range(3, 3 + length[0])
                    )
                    total += sum(
                        c.base_s + c.age_drift_s * age
                        for n, c in zip(length[1:], fitted)
                        for age in range(1, n + 1)
                    )
                    totals.append(total)
        self.assertAlmostEqual(rows[0]["projected_time_s"], min(totals))

    def test_braking_evidence_requires_continuous_same_lap_samples(self):
        rows = [
            {
                "session_time_ms": index * 360,
                "lap_id": "lap",
                "speed_kph": 175,
                "brake_on": True,
                "throttle_pct": 0,
            }
            for index in range(4)
        ]
        self.assertEqual(first_braking_plateau(rows), 1080)
        rows[-1]["lap_id"] = "next"
        self.assertIsNone(first_braking_plateau(rows))

    def test_planner_enforces_observed_age_and_dry_compound_and_set_rules(self):
        medium = Curve("MEDIUM", 80, 0, 18, 0.1)
        hard = Curve("HARD", 80, 0, 18, 0.1)
        plans = plans_to_finish(
            medium, 0, [medium, hard], 57, 0, {"MEDIUM"}, 1, 1, 20, lambda _: 20, 0
        )
        self.assertTrue(plans)
        for plan in plans:
            stops = plan["stops"]
            self.assertEqual(len(stops), 3)
            self.assertIn("HARD", {stop["compound"] for stop in stops})
            breaks = [0, *(stop["lap"] for stop in stops), 57]
            self.assertTrue(
                all(
                    1 <= finish - start <= 18
                    for start, finish in zip(breaks, breaks[1:])
                )
            )
        self.assertEqual(
            plans_to_finish(
                medium, 0, [medium], 12, 0, {"MEDIUM"}, 1, 3, 20, lambda _: 20, 0
            ),
            [],
        )

    def test_stint_drift_is_observed_before_the_cutoff_and_persistent_loss_needs_two_laps(
        self,
    ):
        def lap(age, added=0):
            return {
                "lap_number": age,
                "tyre_life": age,
                "stint_number": 1,
                "compound": "HARD",
                "lap_time_ms": 80000 + age * 200 + added,
                "lap_end_time_ms": age * 90000,
                "track_status": "1",
                "is_accurate": True,
            }

        rows = [lap(age) for age in range(3, 9)]
        rows.extend([lap(9, 1300), lap(10, 1400), lap(11, -60000)])
        weather = [
            {"session_time_ms": row["lap_end_time_ms"], "rainfall": False}
            for row in rows
        ]
        entries = [EntryData("e1", "1", laps=rows), EntryData("e2", "2", laps=rows)]
        data = AnalysisData("s", 0, 10 * 90000, entries=entries, weather=weather)
        fitted = compound_profiles(stint_fits(data, 8 * 90000, "practice"))["HARD"]
        self.assertAlmostEqual(fitted["drift_s_lap"], 0.2)
        self.assertEqual(fitted["observed_age"], 8)
        self.assertGreater(fitted["practice_change_pct"], 0)
        earlier = driver_stint(entries[0], data, 9 * 90000, rows[0], fitted, [])
        later = driver_stint(entries[0], data, 10 * 90000, rows[0], fitted, [])
        self.assertEqual(earlier["persistent_loss_s_lap"], 0)
        self.assertAlmostEqual(later["persistent_loss_s_lap"], 1.35)

    def test_stationary_candidate_is_causal_and_skips_pit_lane(self):
        samples = [{"session_time_ms": x, "speed_kph": 0} for x in range(0, 5500, 500)]
        entry = EntryData("e", "1")
        self.assertEqual(
            _vehicle_warning(entry, samples, 5000)["kind"], "telemetry_stop"
        )
        self.assertIsNone(_vehicle_warning(entry, samples, 9000))
        entry.laps = [{"pit_in_time_ms": 2500}]
        self.assertIsNone(_vehicle_warning(entry, samples, 5000))
