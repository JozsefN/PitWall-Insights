from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
import json
import unittest
import numpy as np
from modules.feature_metrics.domain.analysis.models import AnalysisData, EntryData
from modules.feature_metrics.domain.strategy.models import (
    StrategyRequest,
    StrategyContext,
    TrackProfile,
    Zone,
    TyreCurve,
    TyreSet,
    PitLossModel,
    RuleProfile,
    IncidentHistory,
)
from modules.feature_metrics.domain.strategy.catalog import DEFINITIONS
from modules.feature_metrics.domain.strategy.common import Values
from modules.feature_metrics.domain.strategy.spatial import polygon_clearance
from modules.feature_metrics.domain.strategy.pits import pit_windows
from modules.decision_engine.application.strategy_service import evaluate_strategy


def race_laps(durations, *, offset=0, compound="HARD", initial_age=10):
    clock = offset
    output = []
    for number, seconds in enumerate(durations, 1):
        start = clock
        clock += round(seconds * 1000)
        row = dict(
            id=f"lap-{number}",
            lap_number=number,
            lap_start_time_ms=start,
            lap_end_time_ms=clock,
            lap_time_ms=round(seconds * 1000),
            lap_position=1,
            stint_number=1,
            compound=compound,
            tyre_life=initial_age + number,
            is_accurate=True,
            is_deleted=False,
            is_generated=False,
            pit_in_time_ms=None,
            pit_out_time_ms=None,
            track_status="1",
        )
        for sector in (1, 2, 3):
            row[f"sector_{sector}_session_time_ms"] = round(
                start + (clock - start) * sector / 3
            )
            row[f"sector_{sector}_time_ms"] = round((clock - start) / 3)
        output.append(row)
    return output


def data_fixture(cutoff=390000):
    a = EntryData("a", "1", laps=race_laps([80, 58, 58, 58, 58, 58]))
    b = EntryData("b", "2", laps=race_laps([60] * 6))
    for index, entry in enumerate((a, b)):
        entry.car = [
            dict(session_time_ms=stamp, speed_kph=360, throttle_pct=100, brake_on=False)
            for stamp in range(max(0, cutoff - 180000), cutoff + 1, 1000)
        ]
        entry.positions = [
            dict(
                session_time_ms=stamp,
                x=1000 + (stamp - (cutoff - 180000)) / 1000 * 1000,
                y=1000 + index * 200,
                track_status="OnTrack",
            )
            for stamp in range(max(0, cutoff - 180000), cutoff + 1, 1000)
        ]
    return AnalysisData(
        "test",
        max(0, cutoff - 180000),
        cutoff,
        entries=[a, b],
        track_status=[dict(session_time_ms=0, status="1")],
        coverage={
            "race_start_utc": "2025-01-01T12:00:00+00:00",
            "coordinate_frame": "fastf1:test:xy_metres",
            "position_units_supported": True,
            "season_year": 2025,
        },
    )


def get(response, key, entry="a", rival=None):
    return next(
        row
        for row in response.values
        if row.metric_id == key
        and row.entry_id == entry
        and row.rival_entry_id == rival
    )


def context_fixture():
    return StrategyContext(
        known_at_ms=0,
        source_note="Synthetic, independently specified test assumptions",
        tyre_curves=[
            TyreCurve(
                compound="HARD",
                base_delta_s=0,
                degradation_s_per_lap=0.2,
                max_valid_age_laps=70,
                uncertainty_s_per_lap=0.1,
                provenance="user_scenario",
                source_uri="test:hard",
            ),
            TyreCurve(
                compound="MEDIUM",
                base_delta_s=-0.5,
                degradation_s_per_lap=0.3,
                max_valid_age_laps=30,
                uncertainty_s_per_lap=0.2,
                provenance="user_scenario",
                source_uri="test:medium",
            ),
        ],
        tyre_inventory={
            "a": [
                TyreSet(set_id="medium-one", compound="MEDIUM"),
                TyreSet(set_id="hard-one", compound="HARD"),
            ]
        },
        pit_loss=PitLossModel(
            green_s=20,
            vsc_s=12,
            sc_s=10,
            uncertainty_s=1,
            provenance="user_scenario",
            source_uri="test:pit",
        ),
        rules=RuleProfile(
            profile_id="test-rules",
            season_year=2025,
            minimum_distinct_compounds=2,
            source_uri="test:rules",
        ),
    )


class StrategyMathTests(unittest.TestCase):
    def test_two_stop_optimum_matches_independent_lap_by_lap_enumeration(self):
        data = data_fixture()
        context = context_fixture()
        context.pit_loss.green_s = 2
        context.tyre_curves[0].degradation_s_per_lap = 2
        context.tyre_curves[1].degradation_s_per_lap = 1.5
        result = evaluate_strategy(
            data,
            StrategyRequest(
                as_of_ms=390000, focus_entry_id="a", remaining_laps=8, max_stops=2
            ),
            context,
        )
        base = 58 - 2 * 16
        old = lambda n: sum(base + 2 * (16 + k) for k in range(1, n + 1))
        hard = lambda n: sum(base + 2 * k for k in range(1, n + 1))
        medium = lambda n: sum(base - 0.5 + 1.5 * k for k in range(1, n + 1))
        costs = [old(a) + 2 + medium(8 - a) for a in range(8)]
        for a in range(7):
            for b in range(a + 1, 8):
                costs.extend(
                    [
                        old(a) + hard(b - a) + medium(8 - b) + 4,
                        old(a) + medium(b - a) + hard(8 - b) + 4,
                    ]
                )
        self.assertEqual(len(result.best_modeled_plan.stops), 2)
        self.assertAlmostEqual(
            result.best_modeled_plan.projected_time_s, min(costs), places=5
        )

    def test_already_started_pit_and_finished_race_do_not_generate_pit_now_advice(self):
        data = data_fixture()
        context = context_fixture()
        request = StrategyRequest(as_of_ms=390000, focus_entry_id="a", remaining_laps=8)
        data.entries[0].laps[-1]["pit_in_time_ms"] = 380000
        result = evaluate_strategy(data, request, context)
        self.assertEqual(
            result.recommendation_status, "awaiting_observed_postpit_tyre_state"
        )
        self.assertIsNone(result.best_modeled_plan)
        data.entries[0].laps[-1]["pit_in_time_ms"] = None
        data.coverage["session_phase"] = "Finished"
        finished = evaluate_strategy(data, request, context)
        self.assertEqual(finished.recommendation_status, "session_not_running")
        scenario = evaluate_strategy(
            data, request.model_copy(update={"mode": "counterfactual"}), context
        )
        self.assertIsNotNone(scenario.best_modeled_plan)

    def test_multiple_active_incidents_do_not_multiply_dependent_risks(self):
        data = data_fixture()
        for entry in data.entries:
            for row in entry.car:
                row["speed_kph"] = 0
        result = evaluate_strategy(
            data, StrategyRequest(as_of_ms=390000, focus_entry_id="a")
        )
        self.assertIn("joint incident cohort", result.models["safety_car"]["reason"])
        self.assertIsNone(get(result, "incident_sc_probability_pct", None).value)

    def test_position_teleport_does_not_become_an_offtrack_retirement(self):
        data = data_fixture()
        for row in data.entries[0].car:
            row["speed_kph"] = 0
        data.entries[0].positions[-1]["x"] = 1e9
        result = evaluate_strategy(
            data, StrategyRequest(as_of_ms=390000, focus_entry_id="a")
        )
        self.assertEqual(get(result, "incident_motion_state").value, "stale")
        self.assertIsNone(get(result, "incident_retirement_candidate").value)

    def test_overlapping_sc_vsc_occurrences_are_not_a_false_sum_to_one(self):
        from modules.feature_metrics.domain.strategy.risk import incident_risk

        data = data_fixture()
        context = context_fixture()
        context.track = TrackProfile(
            circuit_key="test",
            coordinate_frame="fastf1:test:xy_metres",
            source_uri="test:track",
            valid_season_from=2025,
            valid_season_to=2025,
        )
        context.incident_history = [
            IncidentHistory(
                observation_id=str(i),
                incident_id=str(i),
                circuit_key="test",
                observed_at_utc=datetime(2024, 1, 1, tzinfo=timezone.utc)
                + timedelta(days=i),
                stopped=True,
                surface="unknown",
                recovery_access="unknown",
                outcome="sc" if i < 30 else "none",
                sc_occurred=i < 30,
                vsc_occurred=i < 30,
                source_uri="test:labels",
            )
            for i in range(40)
        ]
        result = Values(390000)
        state = dict(
            stopped=True,
            collision=False,
            in_pit=False,
            state="stationary_unknown_surface",
            surface="unknown",
            recovery_access="unknown",
            stop_duration_s=5,
        )
        incident_risk(
            data,
            StrategyRequest(as_of_ms=390000, focus_entry_id="a"),
            context,
            state,
            result,
        )
        self.assertAlmostEqual(
            result.get("incident_sc_probability_pct", None), 100 * 31 / 42, places=5
        )
        self.assertGreater(
            result.get("incident_sc_probability_pct", None)
            + result.get("incident_vsc_probability_pct", None),
            100,
        )
        self.assertAlmostEqual(
            sum(result.get("incident_response_distribution_pct", None).values()),
            100,
            places=5,
        )

    def test_matched_gap_closing_rate_catch_time_and_distance(self):
        data = data_fixture(370000)
        result = evaluate_strategy(
            data, StrategyRequest(as_of_ms=370000, focus_entry_id="a")
        )
        self.assertEqual(get(result, "rival_timing_gap_s", rival="b").value, 10)
        self.assertAlmostEqual(
            get(result, "rival_closing_rate_s_per_s", rival="b").value, 2 / 58, places=6
        )
        self.assertAlmostEqual(
            get(result, "rival_catch_time_s", rival="b").value, 290, places=4
        )
        self.assertEqual(
            get(result, "rival_mean_euclidean_distance_m", rival="b").value, 20
        )
        self.assertEqual(get(result, "rival_pair_coverage_pct", rival="b").value, 100)
        self.assertTrue(
            all(point["time_ms"] <= 370000 for point in result.pair_series["b"])
        )

    def test_future_rows_and_current_lap_outcomes_do_not_change_a_past_decision(self):
        data = data_fixture(350000)
        request = StrategyRequest(as_of_ms=350000, focus_entry_id="a")
        before = evaluate_strategy(data, request)
        poisoned = deepcopy(data)
        for entry in poisoned.entries:
            entry.car.append(dict(session_time_ms=9999999, speed_kph=0))
            entry.positions.append(dict(session_time_ms=9999999, x=1e9, y=1e9))
            for lap in entry.laps:
                if lap["lap_end_time_ms"] > 350000:
                    lap.update(
                        compound="FUTURE",
                        tyre_life=999,
                        lap_position=99,
                        lap_time_ms=10000,
                        pit_in_time_ms=9000000,
                    )
            entry.laps.extend(race_laps([1] * 5, offset=10000000))
        poisoned.weather.append(dict(session_time_ms=9000000, wind_speed_kph=300))
        poisoned.track_status.append(dict(session_time_ms=9000000, status="5"))
        after = evaluate_strategy(poisoned, request)
        self.assertEqual(
            [row.model_dump() for row in before.values],
            [row.model_dump() for row in after.values],
        )
        self.assertEqual(before.models, after.models)
        self.assertEqual(before.pair_series, after.pair_series)

    def test_gap_projection_is_suppressed_when_an_unincorporated_pit_stop_occurs(self):
        data = data_fixture()
        data.entries[1].laps[-1]["pit_in_time_ms"] = 380000
        response = evaluate_strategy(
            data, StrategyRequest(as_of_ms=390000, focus_entry_id="a")
        )
        self.assertIsNone(get(response, "rival_projected_gap_s", rival="b").value)
        self.assertEqual(get(response, "rival_timing_gap_s", rival="b").value, 10)

    def test_identifiability_rejects_tyre_age_equal_to_race_lap(self):
        data = data_fixture(900000)
        for entry in data.entries:
            entry.laps = race_laps([60] * 15, initial_age=0)
        result = evaluate_strategy(
            data, StrategyRequest(as_of_ms=900000, focus_entry_id="a")
        )
        self.assertEqual(result.models["pace"]["status"], "unidentifiable")
        self.assertIsNone(get(result, "strategy_compound_age_slopes").value)

    def test_identifiable_driver_compound_age_and_common_trend_ground_truth(self):
        data = data_fixture(2000000)
        for driver, entry in enumerate(data.entries):
            reset = 7 + driver * 3
            durations = []
            for number in range(1, 21):
                age = number if number <= reset else number - reset
                durations.append(
                    60
                    + driver * 0.4
                    + (0 if number <= reset else 0.5)
                    + age * (0.05 if number <= reset else 0.1)
                    - 0.03 * number
                )
            entry.laps = race_laps(durations, initial_age=0)
            for row in entry.laps:
                if row["lap_number"] > reset:
                    row.update(
                        compound="MEDIUM",
                        tyre_life=row["lap_number"] - reset,
                        stint_number=2,
                    )
        result = evaluate_strategy(
            data, StrategyRequest(as_of_ms=2000000, focus_entry_id="a")
        )
        self.assertEqual(
            result.models["pace"]["status"], "identifiable_observational_fit"
        )
        self.assertAlmostEqual(
            get(result, "strategy_common_lap_trend_s_per_lap").value, -0.03, places=5
        )
        slopes = {
            row["compound"]: row["slope_s_per_lap"]
            for row in get(result, "strategy_compound_age_slopes").value
        }
        self.assertAlmostEqual(slopes["HARD"], 0.05, places=5)
        self.assertAlmostEqual(slopes["MEDIUM"], 0.1, places=5)

    def test_bad_rival_stop_counterfactual_does_not_count_the_stop_twice(self):
        data = data_fixture()
        request = StrategyRequest(as_of_ms=390000, focus_entry_id="a")
        result = Values(request.as_of_ms)
        rival_visit = dict(
            entry_id="b",
            phase="1",
            start=100,
            end=130000,
            lane_s=30,
            inlap={"lap_number": 2},
        )
        peers = [
            dict(
                entry_id=f"p{i}",
                phase="1",
                start=100,
                end=125000,
                lane_s=25,
                inlap={"lap_number": 2},
            )
            for i in range(3)
        ]
        pit = dict(loss=20, error=0.1, visits=[*peers, rival_visit], reports=[])
        pit_windows(
            data,
            request,
            None,
            result,
            {"b": dict(gap=-22, error=0.1, anchor_time_ms=300000)},
            pit,
        )
        self.assertEqual(result.get("pit_rejoin_gap_vs_rival_s", "a", "b"), -2)
        self.assertEqual(
            result.get("pit_rival_normal_stop_counterfactual_gap_s", "a", "b"), -17
        )
        self.assertTrue(result.get("pit_rival_delay_creates_window", "a", "b"))
        pit_windows(
            data,
            request,
            None,
            result,
            {"b": dict(gap=-30, error=0.1, anchor_time_ms=300000)},
            pit,
        )
        self.assertFalse(result.get("pit_rival_delay_creates_window", "a", "b"))

    def test_wind_vector_relative_speed_pressure_and_direction_conventions(self):
        data = data_fixture()
        data.weather = [
            dict(
                session_time_ms=390000,
                wind_speed_kph=36,
                wind_direction_deg=270,
                air_temp_c=20,
                pressure_mbar=1013.25,
                humidity_pct=50,
            )
        ]
        context = context_fixture()
        context.track = TrackProfile(
            circuit_key="test",
            coordinate_frame="fastf1:test:xy_metres",
            source_uri="test:survey",
            valid_season_from=2025,
            valid_season_to=2025,
            north_angle_xy_deg=90,
            alignment_error_deg=1,
        )
        result = evaluate_strategy(
            data, StrategyRequest(as_of_ms=390000, focus_entry_id="a"), context
        )
        # Car heads east at 100 m/s. Wind FROM west moves east at 10 m/s: tailwind.
        self.assertAlmostEqual(get(result, "weather_headwind_mps").value, -10, places=5)
        self.assertAlmostEqual(
            get(result, "weather_relative_air_speed_mps").value, 90, places=5
        )
        self.assertAlmostEqual(
            get(result, "weather_dynamic_pressure_change_pct").value, -19, places=5
        )
        rho = get(result, "weather_moist_air_density_kg_m3").value
        self.assertTrue(1.19 < rho < 1.21)
        self.assertAlmostEqual(
            get(result, "weather_dynamic_pressure_pa").value,
            0.5 * rho * 90**2,
            delta=0.01,
        )
        context.track.north_angle_xy_deg = None
        no_alignment = evaluate_strategy(
            data, StrategyRequest(as_of_ms=390000, focus_entry_id="a"), context
        )
        self.assertIsNone(get(no_alignment, "weather_headwind_mps").value)
        self.assertIsNotNone(get(no_alignment, "weather_moist_air_density_kg_m3").value)

    def test_polygon_error_band_and_stale_tracking_are_not_a_retirement(self):
        self.assertEqual(
            polygon_clearance([5, 5], [(0, 0), (10, 0), (10, 10), (0, 10)]), 5
        )
        self.assertEqual(
            polygon_clearance([15, 5], [(0, 0), (10, 0), (10, 10), (0, 10)]), -5
        )
        data = data_fixture()
        data.entries[0].car = data.entries[0].car[:-5]
        data.entries[0].positions = data.entries[0].positions[:-5]
        result = evaluate_strategy(
            data, StrategyRequest(as_of_ms=390000, focus_entry_id="a")
        )
        self.assertEqual(get(result, "incident_motion_state").value, "stale")
        self.assertIsNone(get(result, "incident_retirement_candidate").value)

    def test_empirical_safety_car_distribution_and_no_future_calibration(self):
        data = data_fixture(9000)
        entry = data.entries[0]
        entry.car = [
            dict(session_time_ms=t * 1000, speed_kph=speed)
            for t, speed in enumerate([300, 200, 0, 0, 0, 0, 0, 0, 0, 0])
        ]
        entry.positions = [
            dict(session_time_ms=t * 1000, x=1000, y=1000) for t in range(10)
        ]
        data.track_status.append(dict(session_time_ms=3000, status="2"))
        context = context_fixture()
        context.track = TrackProfile(
            circuit_key="test",
            coordinate_frame="fastf1:test:xy_metres",
            source_uri="test:survey",
            valid_season_from=2025,
            valid_season_to=2025,
            zones=[
                Zone(
                    zone_id="track",
                    kind="racing_surface",
                    polygon_m=[(0, 0), (200, 0), (200, 200), (0, 200)],
                )
            ],
        )
        labels = ["sc"] * 10 + ["vsc"] * 5 + ["red"] * 5 + ["none"] * 20
        context.incident_history = [
            IncidentHistory(
                observation_id=str(i),
                incident_id=str(i),
                circuit_key="test",
                observed_at_utc=datetime(2024, 1, 1, tzinfo=timezone.utc)
                + timedelta(days=i),
                stopped=True,
                surface="on_track",
                recovery_access="unknown",
                outcome=outcome,
                sc_occurred=outcome == "sc",
                vsc_occurred=outcome == "vsc",
                red_occurred=outcome == "red",
                source_uri="test:labels",
            )
            for i, outcome in enumerate(labels)
        ]
        result = evaluate_strategy(
            data, StrategyRequest(as_of_ms=9000, focus_entry_id="a"), context
        )
        self.assertEqual(get(result, "incident_risk_cohort_n", None).value, 40)
        self.assertAlmostEqual(
            get(result, "incident_sc_probability_pct", None).value,
            100 * 11 / 42,
            places=5,
        )
        distribution = get(result, "incident_response_distribution_pct", None).value
        self.assertEqual(distribution["sc"], 25)
        self.assertAlmostEqual(sum(distribution.values()), 100, places=5)
        self.assertEqual(
            get(result, "incident_sc_probability_pct", None).bounds.meaning,
            "credible_interval_95",
        )
        context.incident_history = [
            row.model_copy(
                update={"observed_at_utc": datetime(2026, 1, 1, tzinfo=timezone.utc)}
            )
            for row in context.incident_history
        ]
        result = evaluate_strategy(
            data, StrategyRequest(as_of_ms=9000, focus_entry_id="a"), context
        )
        self.assertIsNone(get(result, "incident_sc_probability_pct", None).value)

    def test_plan_search_inventory_rules_age_limits_and_independent_brute_force_cost(
        self,
    ):
        data = data_fixture()
        context = context_fixture()
        request = StrategyRequest(
            as_of_ms=390000, focus_entry_id="a", remaining_laps=12, max_stops=1
        )
        result = evaluate_strategy(data, request, context)
        self.assertEqual(result.recommendation_status, "conditional_model_ranking")
        self.assertIsNotNone(result.best_modeled_plan)
        self.assertEqual(len(result.best_modeled_plan.stops), 1)
        self.assertEqual(result.best_modeled_plan.stops[0].compound, "MEDIUM")
        current_age = 16
        base = 58 - 0.2 * current_age
        costs = []
        for stop in range(12):
            old = sum(base + 0.2 * (current_age + lap) for lap in range(1, stop + 1))
            new = sum(base - 0.5 + 0.3 * lap for lap in range(1, 13 - stop))
            costs.append(old + 20 + new)
        self.assertAlmostEqual(
            result.best_modeled_plan.projected_time_s, min(costs), places=5
        )
        self.assertEqual(
            result.best_modeled_plan.stops[0].after_laps, int(np.argmin(costs))
        )
        self.assertTrue(all(plan.satisfies_configured_rules for plan in result.plans))
        context.tyre_curves[1].max_valid_age_laps = 1
        constrained = evaluate_strategy(data, request, context)
        self.assertTrue(
            all(plan.stops[0].after_laps == 11 for plan in constrained.plans)
        )

    def test_two_stop_search_never_reuses_a_physical_set(self):
        data = data_fixture()
        context = context_fixture()
        result = evaluate_strategy(
            data,
            StrategyRequest(
                as_of_ms=390000, focus_entry_id="a", remaining_laps=8, max_stops=2
            ),
            context,
        )
        for plan in result.plans:
            ids = [stop.set_id for stop in plan.stops]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(
                all(
                    a.after_laps < b.after_laps
                    for a, b in zip(plan.stops, plan.stops[1:])
                )
            )
        context.tyre_inventory = {}
        missing = evaluate_strategy(
            data,
            StrategyRequest(as_of_ms=390000, focus_entry_id="a", remaining_laps=8),
            context,
        )
        self.assertIsNone(missing.best_modeled_plan)
        self.assertIn("tyre_inventory", missing.models["planning"]["missing"])

    def test_catalogue_completeness_and_finite_json(self):
        result = evaluate_strategy(
            data_fixture(), StrategyRequest(as_of_ms=390000, focus_entry_id="a")
        )
        self.assertEqual({row.metric_id for row in result.values}, set(DEFINITIONS))
        self.assertTrue(
            all(
                row.formula and row.use and row.requires and row.limitations
                for row in DEFINITIONS.values()
            )
        )
        json.dumps(result.model_dump(mode="json"), allow_nan=False)
        with self.assertRaises(ValueError):
            evaluate_strategy(
                data_fixture(),
                StrategyRequest(as_of_ms=390000, focus_entry_id="a"),
                context_fixture().model_copy(update={"known_at_ms": 900000}),
            )
