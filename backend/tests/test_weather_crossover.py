"""Early split, warm-up and tyre crossover regressions over stored OpenF1 examples."""

from collections import defaultdict
from datetime import datetime
from functools import lru_cache
import json
from pathlib import Path
import unittest

from pydantic import ValidationError

from modules.decision_engine.application.replay_strategy_service import RainScenario
from modules.decision_engine.domain.replay_matchup import DriverPlans
from modules.decision_engine.domain.replay_plans import Curve, plans_to_finish
from modules.decision_engine.domain.weather_crossover import (
    comparison_for,
    field_comparison,
    rain_crossover,
)
from modules.feature_metrics.domain.analysis.models import AnalysisData
from modules.feature_metrics.domain.review.replay_sectors import (
    SectorTiming,
    Split,
    warmup_model,
)
from modules.feature_metrics.domain.snapshot import causal_snapshot
from scripts.build_crossover_history import normalize, read_fixture

PIT = {"median_s": 20, "discount_s": {}, "green_basis": "timing_sectors"}
CONTROL = {"phase": "1", "pit_entry_closed": False}
ARCHIVE = json.loads(
    (Path(__file__).parents[2] / "shared/crossover-history.json").read_text()
)["races"]


@lru_cache
def example(key):
    raw = read_fixture(key)
    return normalize(raw), datetime.fromisoformat(raw["date_start"]).timestamp()


def at(key, date):
    (data, reports, out, stamp), before = example(key)
    cutoff = stamp(date)
    timing = SectorTiming(data, causal_snapshot(data, cutoff), reports, out)
    return data, timing, before


def decision(data, timing, before, remaining=8):
    return rain_crossover(
        data,
        timing,
        remaining,
        PIT,
        CONTROL,
        (),
        ARCHIVE,
        before,
        warmup=warmup_model(timing, ARCHIVE, before),
    )


class WeatherCrossoverTests(unittest.TestCase):
    def test_bahrain_exposes_verstappen_outlap_sector_before_lap_end(self):
        data, timing, before = at(10014, "2025-04-13T15:22:14+00:00")
        earlier = at(10014, "2025-04-13T15:21:30+00:00")[1]
        self.assertIsNone(earlier.outlap("1"))
        self.assertNotEqual(earlier.current.get("1"), "HARD")
        reading = timing.outlap("1", warmup_model(timing, ARCHIVE, before))
        self.assertEqual(
            (reading["lap"], reading["sector"], reading["compound"]), (11, 2, "HARD")
        )
        lap = next(
            row
            for entry in data.entries
            if entry.id == "1"
            for row in entry.laps
            if row["lap_number"] == 11
        )
        self.assertGreater(lap["lap_end_time_ms"] - reading["at_ms"], 17_000)

    def test_silverstone_early_slick_scout_before_their_outlap_completes(self):
        data, timing, before = at(9558, "2024-07-07T15:05:50+00:00")
        result = decision(data, timing, before)
        lando = result["decisions"]["4"]
        selection = next(row for row in lando["options"] if row["target"] == "SLICK")
        self.assertEqual(lando["compound"], "INTERMEDIATE")
        self.assertGreaterEqual(selection["scouts"], 2)
        self.assertEqual([row["sector"] for row in selection["sectors"]], [2])
        hamilton = timing.outlap("44", warmup_model(timing, ARCHIVE, before))
        self.assertEqual(hamilton["sector"], 2)
        self.assertGreater(hamilton["at_ms"], 0)

    def test_silverstone_later_pace_favors_slicks(self):
        data, timing, before = at(9558, "2024-07-07T15:06:40+00:00")
        comparison = decision(data, timing, before)["decisions"]["63"]["options"][0]
        self.assertEqual(comparison["target"], "SLICK")
        self.assertEqual({row["sector"] for row in comparison["sectors"]}, {1, 2, 3})
        self.assertGreater(comparison["gain_s_lap"], 1)

    def test_melbourne_late_shower_switches_slick_runners_to_intermediates(self):
        data, timing, before = at(9693, "2025-03-16T05:39:45+00:00")
        crossover = decision(data, timing, before, remaining=11)
        self.assertTrue(crossover["rain_reported"])
        max_call = crossover["decisions"]["1"]
        self.assertEqual(
            (max_call["action"], max_call["target"]), ("box", "INTERMEDIATE")
        )
        self.assertGreater(max_call["options"][0]["gain_s_lap"], 5)
        self.assertEqual(crossover["decisions"]["4"]["compound"], "INTERMEDIATE")

    def test_canada_observes_full_wets_faster_in_early_running(self):
        data, timing, before = at(9531, "2024-06-09T18:06:15+00:00")
        crossover = decision(data, timing, before)
        self.assertEqual(crossover["field"]["WET"], 2)
        option = next(
            row
            for row in crossover["decisions"]["4"]["options"]
            if row["target"] == "WET"
        )
        self.assertEqual(option["scouts"], 2)
        self.assertGreater(option["gain_s_lap"], 1)

    def test_forecast_branches_run_before_anyone_changes_tyres(self):
        data, timing, before = at(10014, "2025-04-13T15:28:00+00:00")
        self.assertEqual(set(timing.current.values()) & {"WET", "INTERMEDIATE"}, set())
        model = dict(
            issued_at_ms=timing.cutoff,
            starts_at_ms=timing.cutoff + 100_000,
            ends_at_ms=timing.cutoff + 540_000,
            probability_pct=90,
            intensity="heavy",
        )
        projection = rain_crossover(
            data, timing, 15, PIT, CONTROL, (), ARCHIVE, before, model
        )
        rows = projection["decisions"]["4"]["options"]
        self.assertEqual({row["target"] for row in rows}, {"INTERMEDIATE", "WET"})
        self.assertTrue(
            all(row["forecast_driven"] and row["scouts"] == 0 for row in rows)
        )
        lower = rain_crossover(
            data,
            timing,
            15,
            PIT,
            CONTROL,
            (),
            ARCHIVE,
            before,
            {**model, "probability_pct": 10},
        )
        for a in rows:
            # Order can change when estimates are close, so compare matched tyres.
            same = next(
                row
                for row in lower["decisions"]["4"]["options"]
                if row["target"] == a["target"]
            )
            self.assertGreater(a["box_s"], same["box_s"])

    def test_fewer_remaining_laps_cannot_amortize_the_same_stop(self):
        data, timing, before = at(9693, "2025-03-16T05:39:45+00:00")
        longer = decision(data, timing, before, remaining=5)["decisions"]["1"][
            "options"
        ][0]
        shorter = decision(data, timing, before, remaining=1)["decisions"]["1"][
            "options"
        ][0]
        self.assertGreater(longer["box_s"], shorter["box_s"])
        self.assertIsNone(shorter["wait_s"])

    def test_pit_closure_blocks_weather_box_choice(self):
        data, timing, before = at(9693, "2025-03-16T05:39:45+00:00")
        control = {**CONTROL, "pit_entry_closed": True}
        result = rain_crossover(data, timing, 5, PIT, control, (), ARCHIVE, before)
        self.assertEqual(result["decisions"]["1"]["action"], "closed")
        self.assertTrue(
            all(row["box_s"] is None for row in result["decisions"]["1"]["options"])
        )

    def test_cold_sector_is_adjusted_once_and_charged_only_if_pit_model_needs_it(self):
        data = AnalysisData("synthetic", 0, 100_000)
        timing = SectorTiming(data, data, [], {})
        timing.current = {"source": "INTERMEDIATE", "cold": "SOFT"}
        timing.latest = {
            driver: ({"lap_start_time_ms": 95_000}, False, None)
            for driver in timing.current
        }
        timing.splits = {
            2: [
                Split("source", 10, 2, 93_000, 31, "INTERMEDIATE", False),
                Split("peer", 10, 2, 94_000, 31, "INTERMEDIATE", False),
                Split("cold", 10, 2, 95_000, 29, "SOFT", True),
                Split("cold2", 10, 2, 96_000, 29, "SOFT", True),
            ]
        }
        timing.by_driver = defaultdict(list)
        warm = {("SLICK", 2): {"loss_s": 2.0}}
        measured = comparison_for(
            field_comparison(timing, warmup=warm), "INTERMEDIATE", "SLICK"
        )[0]
        self.assertEqual(measured[0]["gain_s"], 4.0)
        for method, expected in (("timing_sectors", 18.0), ("whole_laps", 20.0)):
            pit = {**PIT, "median_s": 0, "green_basis": method}
            output = rain_crossover(data, timing, 5, pit, CONTROL, (), warmup=warm)
            choice = output["decisions"]["source"]["options"][0]
            self.assertEqual(choice["box_s"], expected)

    def test_historical_conditions_after_target_race_are_excluded(self):
        data, timing, before = at(10014, "2025-04-13T15:28:00+00:00")
        forecast = dict(
            issued_at_ms=timing.cutoff,
            starts_at_ms=timing.cutoff,
            ends_at_ms=timing.cutoff + 300_000,
            probability_pct=90,
            intensity="rain",
        )
        poisoned = [
            {
                "available_after": before + 1,
                "conditions": {"rain": {"SLICK:INTERMEDIATE": 99}},
            }
        ] * 5
        actual = rain_crossover(
            data, timing, 5, PIT, CONTROL, (), poisoned, before, forecast
        )
        self.assertFalse(actual["decisions"]["4"]["options"])

    def test_forecast_validation_requires_ordered_and_bounded_times(self):
        valid = dict(
            issued_at_ms=1000,
            starts_at_ms=50_000,
            ends_at_ms=100_000,
            probability_pct=80,
            intensity="heavy",
        )
        self.assertEqual(RainScenario(**valid).intensity, "heavy")
        for change in (
            {"starts_at_ms": 0},
            {"ends_at_ms": 1_000_000},
            {"probability_pct": 101},
        ):
            with self.assertRaises(ValidationError):
                RainScenario(**{**valid, **change})

    def test_dry_pace_path_carries_warmup_on_the_lap_after_each_stop(self):
        soft = Curve("SOFT", 80, 0.2, 30, 0.2)
        hard = Curve("HARD", 81, 0.1, 33, 0.2)
        options = [soft, hard]
        args = (soft, 11, options, 16, 20, {"SOFT"}, 1, 1, 21.0, lambda _: 21.0, 0.0)
        raw = plans_to_finish(*args)
        warm = plans_to_finish(*args, warmup_s=1.6)
        early = next(
            row
            for row in warm
            if row["stops"][0]["lap"] == 21 and row["stops"][0]["compound"] == "HARD"
        )
        same = next(row for row in raw if row["stops"] == early["stops"])
        self.assertAlmostEqual(
            early["projected_time_s"] - same["projected_time_s"], 1.6
        )
        model = DriverPlans(
            warm,
            soft,
            {"SOFT": soft, "HARD": hard},
            11,
            20,
            16,
            0.0,
            21.0,
            lambda _: 21.0,
            0.5,
            warmup_s=1.6,
        )
        path = model.path(early)
        self.assertAlmostEqual(path[0][1], 21.0)
        self.assertAlmostEqual(path[1][0], 82.7)
        self.assertAlmostEqual(
            sum(pace + service for pace, service in path), early["projected_time_s"]
        )
