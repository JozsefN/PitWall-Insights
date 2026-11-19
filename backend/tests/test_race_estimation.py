"""Independent numerical and false-positive tests for the uncalibrated race model."""

import copy
import math
import unittest
from dataclasses import replace

from modules.feature_metrics.domain.analysis.models import AnalysisData, EntryData
from modules.feature_metrics.domain.race_estimation.models import (
    RaceEstimateRequest,
    ModelAssumptions,
    RaceContext,
)
from modules.feature_metrics.domain.race_estimation.engine import estimate_race
from modules.feature_metrics.domain.race_estimation.traffic import wake_loss
from modules.feature_metrics.domain.race_estimation.catalog import DEFINITIONS


def fixture(speed=200, brake=False, duration=10000):
    rows = [
        dict(
            session_time_ms=t,
            speed_kph=speed,
            throttle_pct=0 if brake else 100,
            brake_on=brake,
            rpm=10000,
            gear=6,
            drs_state=0,
        )
        for t in range(0, duration + 1, 250)
    ]
    lap = dict(
        id="lap",
        lap_number=1,
        lap_start_time_ms=0,
        lap_end_time_ms=60000,
        lap_time_ms=60000,
        is_accurate=True,
        is_generated=False,
        is_deleted=False,
        compound="SOFT",
        stint_number=1,
        tyre_life=1,
        track_status="1",
    )
    a = EntryData("a", "1", laps=[copy.deepcopy(lap)], car=copy.deepcopy(rows))
    b = EntryData("b", "2", laps=[copy.deepcopy(lap)], car=copy.deepcopy(rows))
    for entry in (a, b):
        entry.positions = [
            dict(
                session_time_ms=r["session_time_ms"],
                x=100 + r["session_time_ms"] / 1000 * speed / 3.6 * 10,
                y=100,
                z=0,
            )
            for r in rows
        ]
    data = AnalysisData(
        "s",
        0,
        duration,
        source="openf1",
        entries=[a, b],
        track_status=[dict(session_time_ms=0, status="1")],
    )
    context = RaceContext(
        driver_ids={"1": "a", "2": "b"},
        positions=[
            dict(session_time_ms=0, driver_number="1", position=1),
            dict(session_time_ms=0, driver_number="2", position=2),
        ],
        intervals=[
            dict(session_time_ms=t, driver_number="2", interval=0.4)
            for t in range(0, duration + 1, 2000)
        ],
    )
    return data, context, RaceEstimateRequest(as_of_ms=duration, lookback_ms=30000)


def metric(response, key, driver="b"):
    return next(d for d in response.drivers if d.entry_id == driver).metrics[key]


class RacePhysicsTests(unittest.TestCase):
    def test_wake_availability_explains_the_finish_and_missing_current_speed(self):
        data, context, _ = fixture()
        data.race_control.append(
            {"session_time_ms": 9000, "scope": "Track", "flag": "CHEQUERED"}
        )
        for entry in data.entries:
            entry.car = []
        observed = estimate_race(data, context, RaceEstimateRequest(as_of_ms=10000))
        estimates = observed.drivers[0].metrics
        self.assertEqual(
            estimates["wake_loss_scenario_pct"].unavailable_cause, "outside_window"
        )
        self.assertIn("race has finished", estimates["wake_loss_scenario_pct"].reason)
        self.assertEqual(
            estimates["current_speed_kph"].unavailable_cause, "missing_data"
        )

    def test_wake_anchors_monotonicity_and_boundedness(self):
        assumptions = ModelAssumptions()
        self.assertAlmostEqual(wake_loss(10, assumptions), 18, places=8)
        self.assertAlmostEqual(wake_loss(20, assumptions), 4, delta=0.02)
        values = [wake_loss(d, assumptions) for d in range(0, 100)]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertTrue(all(0 <= v <= 35 for v in values))

    def test_same_time_gap_does_not_imply_same_distance_or_wake_loss(self):
        slow = estimate_race(*fixture(speed=80))
        fast = estimate_race(*fixture(speed=250))
        self.assertLess(
            metric(slow, "ahead_distance_scenario_m").value,
            metric(fast, "ahead_distance_scenario_m").value,
        )
        self.assertGreater(
            metric(slow, "wake_loss_scenario_pct").value,
            metric(fast, "wake_loss_scenario_pct").value,
        )
        self.assertIsNone(metric(slow, "traffic_correlated_loss_s").value)

    def test_aerodynamic_load_scales_with_velocity_squared(self):
        a = estimate_race(*fixture(speed=100))
        b = estimate_race(*fixture(speed=200))
        self.assertAlmostEqual(
            metric(b, "aero_load_ratio").value,
            4 * metric(a, "aero_load_ratio").value,
            places=5,
        )

    def test_braking_energy_has_mass_specific_kinetic_units(self):
        data, context, request = fixture(duration=4000, brake=True)
        for entry in data.entries:
            for row in entry.car:
                row["speed_kph"] = 400 - 200 * row["session_time_ms"] / 4000
        response = estimate_race(data, context, request)
        expected = 0.5 * ((400 / 3.6) ** 2 - (200 / 3.6) ** 2) / 1000
        self.assertAlmostEqual(
            metric(response, "braking_kinetic_loss_kjkg").value, expected, places=5
        )
        self.assertAlmostEqual(
            metric(response, "mean_braking_deceleration_g").value,
            (200 / 3.6) / 4 / 9.80665,
            places=5,
        )

    def test_no_unknown_north_or_wind_convention_is_silently_assumed(self):
        data, context, request = fixture()
        data.weather = [
            dict(
                session_time_ms=0,
                air_temp_c=20,
                pressure_mbar=1013.25,
                wind_speed_kph=36,
                wind_direction_deg=90,
            )
        ]
        result = estimate_race(data, context, request)
        self.assertIsNone(metric(result, "headwind_ms").value)
        self.assertAlmostEqual(
            metric(result, "air_density_kgm3").value,
            101325 / (287.05 * 293.15),
            places=5,
        )
        self.assertEqual(metric(result, "relative_air_speed_low_kph").value, 164)
        request.assumptions.north_rotation_deg = 0
        self.assertIsNone(
            metric(estimate_race(data, context, request), "headwind_ms").value
        )
        request.assumptions.wind_direction_is_from = True
        self.assertAlmostEqual(
            metric(estimate_race(data, context, request), "headwind_ms").value,
            10,
            places=5,
        )

    def test_plateau_under_braking_is_only_a_weak_anomaly(self):
        response = estimate_race(*fixture(brake=True))
        candidates = [e for e in response.events if e.kind == "braking_anomaly"]
        self.assertEqual(len(candidates), 2)
        self.assertTrue(
            all(e.classification == "candidate" and e.support < 0.5 for e in candidates)
        )
        self.assertFalse(
            any(
                "confirmed" in e.title.lower() or e.kind == "lock_up"
                for e in response.events
            )
        )
        self.assertFalse(any(e.kind == "possible_incident" for e in response.events))

    def test_wind_vector_pressure_and_headway_means_have_physical_units(self):
        data, context, request = fixture()
        data.weather = [
            dict(
                session_time_ms=0,
                air_temp_c=20,
                pressure_mbar=1013.25,
                wind_speed_kph=36,
                wind_direction_deg=90,
            )
        ]
        unaligned = estimate_race(data, context, request)
        self.assertIsNone(metric(unaligned, "relative_air_speed_kph").value)
        self.assertAlmostEqual(metric(unaligned, "mean_ahead_gap_s").value, 0.4)
        self.assertAlmostEqual(
            metric(unaligned, "mean_headway_distance_m").value,
            0.4 * 200 / 3.6,
            places=5,
        )
        request.assumptions.north_rotation_deg = 0
        request.assumptions.wind_direction_is_from = True
        aligned = estimate_race(data, context, request)
        self.assertAlmostEqual(
            metric(aligned, "relative_air_speed_kph").value, 236, places=5
        )
        self.assertAlmostEqual(metric(aligned, "crosswind_ms").value, 0, places=5)
        self.assertAlmostEqual(
            metric(aligned, "wind_pressure_shift_pct").value,
            100 * ((236 / 200) ** 2 - 1),
            places=5,
        )
        density = 101325 / (287.05 * 293.15)
        self.assertAlmostEqual(
            metric(aligned, "dynamic_pressure_pa").value,
            0.5 * density * (236 / 3.6) ** 2,
            places=5,
        )
        self.assertGreater(
            metric(aligned, "aero_load_ratio").value,
            metric(unaligned, "aero_load_ratio").value,
        )

    def test_missing_geometry_does_not_become_zero_tyre_workload(self):
        data, context, request = fixture()
        for entry in data.entries:
            entry.positions = []
        result = estimate_race(data, context, request)
        for key in (
            "corner_load_index",
            "tyre_thermal_load_index",
            "wear_pressure_index",
        ):
            self.assertIsNone(metric(result, key).value)
        self.assertIsNone(metric(result, "defence_pressure_index", driver="b").value)

    def test_target_change_or_stale_gap_cannot_be_a_closing_trend(self):
        data, context, request = fixture(duration=30000)
        context.positions.extend(
            [
                dict(session_time_ms=12000, driver_number="1", position=3),
                dict(session_time_ms=12000, driver_number="3", position=1),
            ]
        )
        result = estimate_race(data, context, request)
        self.assertIsNone(metric(result, "gap_closing_rate").value)
        context.positions = context.positions[:2]
        context.intervals = [
            row for row in context.intervals if row["session_time_ms"] <= 10000
        ]
        result = estimate_race(data, context, request)
        self.assertIsNone(metric(result, "gap_closing_rate").value)

    def test_real_stop_needs_fresh_samples_and_prestart_is_excluded(self):
        data, context, request = fixture(speed=0)
        self.assertTrue(
            any(
                e.kind == "stopped_car"
                for e in estimate_race(data, context, request).events
            )
        )
        for entry in data.entries:
            entry.laps[0]["lap_start_time_ms"] = 20000
        self.assertFalse(
            any(
                e.kind == "stopped_car"
                for e in estimate_race(data, context, request).events
            )
        )

    def test_stale_or_sparse_packets_do_not_become_a_sustained_stop(self):
        data, context, request = fixture(speed=0)
        for entry in data.entries:
            entry.car = [entry.car[0], entry.car[-1]]
        response = estimate_race(data, context, request)
        self.assertFalse(any(e.kind == "stopped_car" for e in response.events))
        request.as_of_ms += 10000
        self.assertIsNone(
            metric(estimate_race(data, context, request), "current_speed_kph").value
        )
        self.assertIsNone(
            metric(estimate_race(data, context, request), "current_stopped_s").value
        )

    def test_pit_and_neutralisation_do_not_create_wake_or_incident_claims(self):
        data, context, request = fixture(speed=0)
        for entry in data.entries:
            entry.laps[0]["pit_in_time_ms"] = 0
        response = estimate_race(data, context, request)
        self.assertFalse(
            any(e.kind in ("stopped_car", "possible_incident") for e in response.events)
        )
        data, context, request = fixture()
        data.track_status = [dict(session_time_ms=0, status="4")]
        response = estimate_race(data, context, request)
        self.assertIsNone(metric(response, "wake_loss_scenario_pct").value)
        self.assertIsNone(metric(response, "attack_opportunity_index").value)
        self.assertAlmostEqual(metric(response, "pit_loss_scenario_s").value, 22 * 0.55)

    def test_lapping_or_adjacent_hairpin_geometry_is_not_close_following(self):
        data, context, request = fixture()
        for row in context.intervals:
            row["interval"] = "+1 LAP"
        response = estimate_race(data, context, request)
        self.assertIsNone(metric(response, "close_following_s").value)
        self.assertIsNone(metric(response, "wake_loss_scenario_pct").value)
        for row in context.intervals:
            row["interval"] = 20
        self.assertEqual(
            metric(estimate_race(data, context, request), "close_following_s").value, 0
        )

    def test_future_inputs_and_lap_outcomes_cannot_change_prefix_result(self):
        data, context, request = fixture()
        before = estimate_race(data, context, request).model_dump()
        future = copy.deepcopy(data)
        for entry in future.entries:
            entry.car.append(
                dict(
                    session_time_ms=20000,
                    speed_kph=450,
                    brake_on=False,
                    throttle_pct=100,
                )
            )
            entry.laps[0].update(
                lap_time_ms=1, is_deleted=True, compound="HARD", tyre_life=99
            )
        future.race_control.append(
            dict(session_time_ms=20000, message="RED FLAG", flag="RED")
        )
        context.intervals.append(
            dict(session_time_ms=20000, driver_number="2", interval=0.01)
        )
        after = estimate_race(future, context, request).model_dump()
        self.assertEqual(before, after)

    def test_pit_duration_is_not_available_before_conservative_publication_time(self):
        data, context, request = fixture()
        context.pits = [dict(session_time_ms=5000, driver_number="2", pit_duration=25)]
        response = estimate_race(data, context, request)
        self.assertFalse(any(e.kind == "pit_stop" for e in response.events))
        self.assertIsNone(metric(response, "pit_lane_duration_median_s").value)

    def test_unknown_driver_rejected_and_all_results_json_finite(self):
        data, context, request = fixture()
        request.entry_ids = ["unknown"]
        with self.assertRaises(ValueError):
            estimate_race(data, context, request)
        request.entry_ids = ["b"]
        response = estimate_race(data, context, request)
        self.assertEqual(len(response.drivers), 1)
        self.assertEqual(set(response.drivers[0].metrics), set(DEFINITIONS))
        import json

        json.dumps(response.model_dump(), allow_nan=False)

    def test_reported_flag_is_delayed_until_known_and_native_rank_does_not_expire(self):
        data, context, request = fixture(duration=200000)
        data.race_control = [
            dict(session_time_ms=199500, message="YELLOW FLAG", flag="YELLOW")
        ]
        response = estimate_race(data, context, request)
        self.assertFalse(any(e.kind == "yellow_flag" for e in response.events))
        self.assertEqual(
            next(d for d in response.drivers if d.entry_id == "b").ahead_entry_id, "a"
        )
        request.as_of_ms = 201000
        self.assertTrue(
            any(
                e.kind == "yellow_flag"
                for e in estimate_race(data, context, request).events
            )
        )
