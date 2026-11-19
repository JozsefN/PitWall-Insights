"""Offline replay regressions from professional strategy debriefs and OpenF1 timing."""

import gzip
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from statistics import median
import unittest

from modules.decision_engine.domain.replay_plans import Curve, plans_to_finish
from modules.feature_metrics.domain.review.intervention import current_race_control
from modules.feature_metrics.domain.review.replay_pit import archive_stop_ratio
from modules.feature_metrics.domain.source_clock import timed_rows
from modules.normalization.domain.openf1_quality import derive_track_status
from scripts.build_pit_sector_archive import sector_observations

FIXTURES = Path(__file__).parent / "fixtures/strategy_cases"
ARCHIVE = Path(__file__).resolve().parents[2] / "shared/pit-sector-loss.json"


@lru_cache
def race(key):
    with gzip.open(FIXTURES / f"{key}.json.gz", "rt", encoding="utf-8") as stream:
        return json.load(stream)


def instant(data, date):
    return round(
        (
            datetime.fromisoformat(date) - datetime.fromisoformat(data["date_start"])
        ).total_seconds()
        * 1000
    )


def controls_at(data, date):
    return [
        row
        for row in timed_rows(
            data["race_control"], datetime.fromisoformat(data["date_start"])
        )
        if row["session_time_ms"] <= instant(data, date)
    ]


@lru_cache
def observations(key, cutoff=None):
    data = race(key)
    finish = next(
        row["date"] for row in data["race_control"] if row.get("flag") == "CHEQUERED"
    )
    return sector_observations(
        data["laps"],
        data["pit"],
        data["race_control"],
        datetime.fromisoformat(data["date_start"]),
        cutoff if cutoff is not None else instant(data, finish),
    )


def measured(key, phase):
    return median(
        row["net_loss_s"] for row in observations(key) if row["phase"] == phase
    )


class ProfessionalStrategyCases(unittest.TestCase):
    def test_imola_green_stop_model_agrees_with_pirelli_pre_race_estimate(self):
        # Pirelli identified a roughly 27-second green stop cost in its Friday debrief.
        self.assertAlmostEqual(measured(9987, "green"), 27, delta=2.0)

    def test_imola_vsc_reduces_measured_stop_loss(self):
        # Timing-sector comparisons of the stable VSC cohort, across several teams.
        self.assertGreater(measured(9987, "green") - measured(9987, "vsc"), 4.0)
        self.assertLess(measured(9987, "vsc"), measured(9987, "sc"))

    def test_imola_model_allows_leaving_an_aged_set_at_next_open_entry(self):
        medium = Curve("MEDIUM", 80, 0.12, 28, 0.2)
        hard = Curve("HARD", 81, 0.04, 39, 0.2)
        args = (
            medium,
            28,
            [medium, hard],
            35,
            28,
            {"MEDIUM"},
            1,
            1,
            27,
            lambda _: 22,
            0,
        )
        self.assertFalse(plans_to_finish(*args))
        plans = plans_to_finish(*args, allow_exit_at_observed_limit=True)
        self.assertTrue(plans)
        self.assertTrue(
            all(
                plan["stops"][0]["lap"] == 29 and plan["exit_lap_beyond_observed_age"]
                for plan in plans
            )
        )
        self.assertFalse(
            plans_to_finish(
                *args, earliest_first_stop=2, allow_exit_at_observed_limit=True
            )
        )

    def test_imola_norris_pits_under_green_and_verstappen_under_vsc(self):
        data = race(9987)
        norris = next(row for row in data["pit"] if row["driver_number"] == 4)
        verstappen = next(row for row in data["pit"] if row["driver_number"] == 1)
        self.assertEqual(
            current_race_control(controls_at(data, norris["date"])), (None, False)
        )
        self.assertEqual(
            current_race_control(controls_at(data, verstappen["date"])), ("6", False)
        )
        self.assertLess(
            instant(data, norris["date"]), instant(data, verstappen["date"])
        )

    def test_imola_warning_cutoff_cannot_use_unfinished_vsc_stops(self):
        data = race(9987)
        cutoff = instant(data, "2025-05-18T13:42:33+00:00")
        rows = observations(9987, cutoff)
        self.assertTrue(rows)
        self.assertTrue(
            all(
                row["phase"] == "green" and row["known_at_ms"] <= cutoff for row in rows
            )
        )

    def test_bahrain_green_cost_is_close_to_published_estimate(self):
        self.assertAlmostEqual(measured(10014, "green"), 22.9, delta=1.5)

    def test_bahrain_slow_red_bull_service_is_visible_in_pit_timing(self):
        data = race(10014)
        stops = [p for p in data["pit"] if p["driver_number"] == 1]
        self.assertEqual([row["lap_number"] for row in stops], [10, 26])
        self.assertEqual([row["stop_duration"] for row in stops], [4.7, 6.2])
        self.assertGreater(stops[-1]["lane_duration"], 27.0)

    def test_bahrain_piastri_stop_is_classified_in_the_actual_safety_car_phase(self):
        data = race(10014)
        piastri = [p for p in data["pit"] if p["driver_number"] == 81]
        self.assertEqual(
            [
                current_race_control(controls_at(data, row["date"]))[0]
                for row in piastri
            ],
            [None, "4"],
        )
        self.assertGreater(measured(10014, "green") - measured(10014, "sc"), 2.0)

    def test_miami_mclaren_double_stack_is_observed_during_vsc(self):
        data = race(10033)
        pair = [p for p in data["pit"] if p["driver_number"] in (4, 81)]
        self.assertEqual([row["driver_number"] for row in pair], [81, 4])
        self.assertEqual([row["lap_number"] for row in pair], [29, 29])
        self.assertAlmostEqual(
            (instant(data, pair[1]["date"]) - instant(data, pair[0]["date"])) / 1000,
            11.46,
            delta=0.2,
        )
        self.assertTrue(
            all(
                current_race_control(controls_at(data, row["date"]))[0] == "6"
                for row in pair
            )
        )

    def test_melbourne_abbreviated_vsc_is_normalized_and_ending_is_causal(self):
        data = race(11234)
        prefix = controls_at(data, "2026-03-08T04:19:07+00:00")
        self.assertIsNone(current_race_control(prefix)[0])
        after = controls_at(data, "2026-03-08T04:19:08+00:00")
        self.assertEqual(current_race_control(after)[0], "6")
        events = derive_track_status(
            [
                {
                    "SessionTime": row["session_time_ms"],
                    "Message": row["message"],
                    "Flag": row["flag"],
                    "Scope": row["scope"],
                    "Sector": row["sector"],
                }
                for row in after
            ]
        )
        self.assertEqual(events[-1]["Status"], "6")
        self.assertEqual(
            current_race_control(controls_at(data, "2026-03-08T04:23:07+00:00"))[0], "7"
        )

    def test_melbourne_ferrari_second_window_closes_and_reopens_at_reported_times(self):
        data = race(11234)
        self.assertEqual(
            current_race_control(controls_at(data, "2026-03-08T04:31:15+00:00")),
            ("6", False),
        )
        self.assertEqual(
            current_race_control(controls_at(data, "2026-03-08T04:31:16+00:00")),
            ("6", True),
        )
        self.assertEqual(
            current_race_control(controls_at(data, "2026-03-08T04:32:20+00:00")),
            ("6", True),
        )
        self.assertEqual(
            current_race_control(controls_at(data, "2026-03-08T04:32:21+00:00")),
            ("6", False),
        )

    def test_melbourne_measured_vsc_saving_matches_debrief_scale(self):
        saving = measured(11234, "green") - measured(11234, "vsc")
        self.assertAlmostEqual(saving, 10.0, delta=2.0)

    def test_melbourne_closed_entry_removes_even_a_cheap_immediate_stop(self):
        data = race(11234)
        _, closed = current_race_control(controls_at(data, "2026-03-08T04:31:16+00:00"))
        medium = Curve("MEDIUM", 85.0, 0.3, 40, 0.3)
        hard = Curve("HARD", 85.5, 0.1, 40, 0.3)
        args = (
            medium,
            18,
            [medium, hard],
            35,
            18,
            {"MEDIUM"},
            1,
            1,
            21.0,
            lambda _: 8.0,
            0.0,
        )
        open_plans = plans_to_finish(*args)
        closed_plans = plans_to_finish(*args, earliest_first_stop=2 if closed else 1)
        self.assertTrue(any(plan["stops"][0]["lap"] == 19 for plan in open_plans))
        self.assertTrue(closed_plans)
        self.assertTrue(all(plan["stops"][0]["lap"] >= 20 for plan in closed_plans))

    def test_chronological_archive_predicts_imola_vsc_cost_better_than_green_baseline(
        self,
    ):
        data = race(9987)
        start = datetime.fromisoformat(data["date_start"]).timestamp()
        prior = [
            row
            for row in json.loads(ARCHIVE.read_text())["races"]
            if row["available_after"] < start
        ]
        green = median(
            row["phases"]["green"]["median_s"]
            for row in prior
            if row["circuit"] == data["circuit_key"] and "green" in row["phases"]
        )
        ratio, basis = archive_stop_ratio(prior, data["circuit_key"], "vsc")
        self.assertGreaterEqual(basis["samples"], 3)
        observed = measured(9987, "vsc")
        self.assertLess(abs(green * ratio - observed), abs(green - observed))
        self.assertAlmostEqual(green * ratio, observed, delta=4.0)
