import unittest

from modules.decision_engine.domain.replay_matchup import (
    DriverPlans,
    duel_path,
    duel_scenarios,
    slow_stop_window,
)
from modules.decision_engine.domain.replay_plans import Curve, plans_to_finish
from modules.feature_metrics.domain.analysis.models import AnalysisData, EntryData
from modules.feature_metrics.domain.review.intervention import (
    phase_at_pit,
    probability_forecast,
    race_episodes,
)
from modules.feature_metrics.domain.review.replay_rivals import SECTORS, replay_rivals
from modules.feature_metrics.domain.review.replay_tyres import (
    StintFit,
    compound_offsets,
)


def lap(number, pace_delta=0, finish_delay=0):
    end = number * 90_000 + finish_delay
    return {
        "lap_number": number,
        "lap_start_time_ms": end - 80_000,
        "lap_end_time_ms": end,
        "lap_time_ms": 80_000 + pace_delta,
        "is_accurate": True,
        "track_status": "1",
        **dict(zip(SECTORS, (28_000 + pace_delta, 27_000, 25_000))),
    }


class Timing:
    def gaps(self, entries, stamp):
        return {"own": 2.0, "rival": 3.0, "other": 15.0}, {}


class ReplayRivalsTests(unittest.TestCase):
    def test_unmatched_practice_runs_do_not_become_compound_offsets(self):
        def run(driver, compound, pace):
            return StintFit(
                driver, "practice", "practice", compound, 3, 16, 14, 0.1, pace, 0.2, 1
            )

        fits = [
            run(driver, compound, pace)
            for driver, paces in (
                ("a", (95, 96)),
                ("b", (97, 98)),
                ("c", (118, 96)),
                ("d", (121, 97)),
            )
            for compound, pace in zip(("HARD", "MEDIUM"), paces)
        ]
        self.assertEqual(compound_offsets(fits)[("HARD", "MEDIUM")], (1.0, 0.0, 2))
        self.assertEqual(compound_offsets(fits[4:]), {})

    def test_pre_stop_rival_survives_grid_penalty_and_pit_drop(self):
        own = EntryData(
            "own", "1", grid_position=16, laps=[lap(n, 150) for n in range(1, 6)]
        )
        rival = EntryData(
            "rival",
            "2",
            grid_position=2,
            laps=[
                lap(1),
                lap(2, finish_delay=39_000),
                lap(3),
                lap(4),
                lap(5, -7_000),
            ],
        )
        other = EntryData(
            "other", "3", grid_position=15, laps=[lap(n, 900) for n in range(1, 5)]
        )
        data = AnalysisData("race", 0, 440_000, entries=[own, rival, other])
        pit = {
            "entry_id": "rival",
            "event_time_ms": 375_000,
            "known_at_ms": 410_000,
            "lane_duration_s": 20.0,
        }
        grid = {"own": 2.0, "rival": 35.0, "other": 5.0}
        standings = {"1": [3, 80], "2": [4, 77], "3": [16, 0]}

        before, _ = replay_rivals(data, 400_000, Timing(), grid, [pit], standings, {})
        self.assertNotIn("rival", [row["entry_id"] for row in before["own"]])
        after, _ = replay_rivals(data, 440_000, Timing(), grid, [pit], standings, {})
        matched = after["own"][0]
        self.assertEqual(matched["entry_id"], "rival")
        self.assertEqual(matched["gap_s"], -33.0)
        self.assertEqual(matched["pre_pit_gap_s"], -1.0)
        self.assertEqual(matched["grid_gap"], 14)
        self.assertEqual(matched["championship_before"], [4, 77])
        self.assertEqual(matched["comparison"]["laps"], 3)
        self.assertEqual(matched["comparison"]["last_lap"], 4)
        self.assertEqual(
            [row["delta_s"] for row in matched["comparison"]["sectors"]], [0.15, 0, 0]
        )
        expired, _ = replay_rivals(data, 780_000, Timing(), grid, [pit], standings, {})
        self.assertNotIn("rival", [row["entry_id"] for row in expired["own"]])

    def test_following_loss_and_pace_after_pitting(self):
        gap, delay = duel_path(
            [(80, 0), (79, 22), (78, 0)], [(81, 0), (80, 0), (80, 0)], 0.6, 0.5
        )
        self.assertAlmostEqual(delay, 0.5)
        self.assertAlmostEqual(gap[-1], 19.1)

        old = Curve("MEDIUM", 80, 0.3, 30, 0.2)
        fresh = Curve("HARD", 79, 0.1, 30, 0.2)
        curves = {curve.compound: curve for curve in (old, fresh)}

        def model(age):
            plans = plans_to_finish(
                old,
                age,
                [old, fresh],
                8,
                32,
                {"MEDIUM", "HARD"},
                2,
                1,
                18,
                lambda _: 18,
                0,
            )
            return DriverPlans(plans, old, curves, age, 32, 8, 0, 18, lambda _: 18, 0.5)

        rows, _ = duel_scenarios(
            "own",
            "rival",
            model(15),
            model(10),
            {"own": 5.6, "rival": 5, "third": 10, "fourth": 14},
            0.5,
        )
        by_branch = {row["assumption"]: row for row in rows}
        self.assertEqual(set(by_branch), {"holds", "boxes", "finishes"})
        box_holds = next(
            row for row in by_branch["holds"]["choices"] if row["action"] == "box"
        )
        box_matches = next(
            row for row in by_branch["boxes"]["choices"] if row["action"] == "box"
        )
        self.assertEqual(box_holds["positions_lost"], 2)
        self.assertGreater(
            box_holds["post_pit_pace_advantage_s"],
            box_matches["post_pit_pace_advantage_s"],
        )
        self.assertAlmostEqual(box_holds["finish_margin_s"], 1.8)
        self.assertAlmostEqual(box_matches["finish_margin_s"], -2.1)

    def test_slow_stop_window_requires_a_real_rejoin_flip(self):
        excess = {
            "basis": "stationary",
            "excess_s": 5.0,
            "scatter_s": 0.4,
            "samples": 9,
        }
        result = slow_stop_window(-22, 20, excess, 1.0)
        self.assertEqual((result["margin_s"], result["normal_margin_s"]), (2.0, -3.0))
        self.assertIsNone(slow_stop_window(-21, 20, excess, 1.0))
        self.assertIsNone(slow_stop_window(-29, 20, excess, 1.0))
        self.assertIsNone(slow_stop_window(-22, 20, None, 1.0))

    def test_forecast_is_used_at_pit_and_respects_vsc_to_sc_timeline(self):
        def entry(race, converted):
            return {
                "race": race,
                "coverage_s": 250,
                "outcome": "vsc" if converted else None,
                "response_s": 15 if converted else None,
                "phases": [["vsc", 15, 35], ["sc", 35, 110]] if converted else [],
            }

        cohort = [entry(n, n < 6) for n in range(12)]
        reference = cohort + [entry(n, False) for n in range(12, 52)]
        raw = probability_forecast(cohort, 10, "pooled")
        regularized = probability_forecast(cohort, 10, "pooled", reference)
        vsc = regularized["outcomes_pct"]["vsc"] / 100
        self.assertLess(vsc, raw["outcomes_pct"]["vsc"] / 100)
        self.assertEqual(
            phase_at_pit(cohort, 10, 10, regularized), {"sc": 0, "vsc": vsc}
        )
        self.assertEqual(
            phase_at_pit(cohort, 10, 45, regularized), {"sc": vsc, "vsc": 0}
        )
        self.assertEqual(
            phase_at_pit(cohort, 10, 105, regularized), {"sc": 0, "vsc": 0}
        )
        self.assertEqual(phase_at_pit(cohort, 10, 121, regularized), {})

    def test_local_clear_only_closes_an_episode_once_all_yellows_clear(self):
        def flag(stamp, name, sector=None):
            return {
                "session_time_ms": stamp,
                "flag": name,
                "scope": "Sector" if sector else "Track",
                "sector": sector,
            }

        rows = [
            flag(1, "YELLOW", 2),
            flag(2, "DOUBLE YELLOW", 3),
            flag(3, "CLEAR", 2),
            flag(4, "CLEAR", 3),
        ]
        self.assertIsNone(race_episodes(rows[:3], 0)[0].clear_ms)
        self.assertEqual(race_episodes(rows, 0)[0].clear_ms, 4)
        self.assertIsNone(race_episodes([flag(0, "YELLOW"), *rows], 0)[0].clear_ms)
