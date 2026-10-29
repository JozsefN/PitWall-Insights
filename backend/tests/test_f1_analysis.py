"""Physical ground truths and failure cases, rather than snapshotting implementation output."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import math
import unittest
from unittest.mock import patch
import numpy as np

from modules.feature_metrics.domain.analysis.catalog import DEFINITIONS
from modules.feature_metrics.domain.analysis.models import (
    AnalysisData,
    EntryData,
    AnalysisRequest,
)
from modules.feature_metrics.domain.analysis.engine import analyze
from modules.feature_metrics.domain.analysis.geometry import ReferenceLine
from modules.feature_metrics.domain.analysis.common import aligned_values
from modules.feature_metrics.domain.analysis.common import Results
from modules.normalization.application.service import NormalizationService
from support import source_bundle


def lap(number, duration=60000, **values):
    return dict(
        id=str(number),
        lap_number=number,
        lap_start_time_ms=(number - 1) * 60000,
        lap_end_time_ms=number * 60000,
        lap_time_ms=duration,
        sector_1_time_ms=duration / 3,
        sector_2_time_ms=duration / 3,
        sector_3_time_ms=duration / 3,
        is_accurate=True,
        is_generated=False,
        is_deleted=False,
        track_status="1",
        stint_number=1,
        tyre_life=number,
        compound="SOFT",
        lap_position=2,
        **values
    )


def straight_data(seconds=60):
    times = range(seconds)
    entry = EntryData("one", "1", grid_position=4, laps=[lap(1)])
    entry.car = [
        dict(
            session_time_ms=t * 1000,
            speed_kph=60,
            throttle_pct=100,
            brake_on=False,
            gear=6,
            rpm=10000,
            drs_state=12,
        )
        for t in times
    ]
    entry.positions = [
        dict(
            session_time_ms=t * 1000,
            x=1000 + t * 60 / 3.6 * 10,
            y=1000,
            z=0,
            track_status="OnTrack",
        )
        for t in times
    ]
    return AnalysisData(
        "test",
        0,
        seconds * 1000,
        entries=[entry],
        track_status=[dict(session_time_ms=0, status="1")],
    )


def metric(response, key, entry="one"):
    return next(
        row
        for row in response.metrics
        if row.metric_id == key and row.entry_id == entry
    )


class FormulaTests(unittest.TestCase):
    def test_constant_speed_units_distance_controls_and_no_false_incident(self):
        response = analyze(straight_data(), AnalysisRequest())
        for key, expected in {
            "mean_speed_kph": 60,
            "integrated_distance_m": 59 * 60 / 3.6,
            "position_distance_m": 59 * 60 / 3.6,
            "mean_position_speed_kph": 60,
            "full_throttle_pct": 100,
            "mean_throttle_pct": 100,
            "braking_pct": 0,
            "reported_drs_open_pct": 100,
            "gear_6_time_pct": 100,
            "observed_gear_changes": 0,
            "car_time_coverage_pct": 100,
            "possible_incident_count": 0,
            "positions_gained_from_grid": 2,
            "best_lap_ms": 60000,
        }.items():
            self.assertAlmostEqual(
                metric(response, key).value, expected, places=5, msg=key
            )
        self.assertEqual(len(response.metrics), len(DEFINITIONS))
        self.assertFalse(
            any(event.kind == "possible_incident" for event in response.events)
        )
        json.dumps(response.model_dump(mode="json"), allow_nan=False)

    def test_acceleration_and_braking_energy_have_physical_units(self):
        data = straight_data(11)
        for index, row in enumerate(data.entries[0].car):
            row.update(speed_kph=index * 36, brake_on=False)
        response = analyze(data, AnalysisRequest(groups=["speed"]))
        self.assertAlmostEqual(
            metric(response, "max_acceleration_g").value, 10 / 9.80665, places=6
        )
        self.assertAlmostEqual(
            metric(response, "integrated_distance_m").value, 500, places=5
        )
        for index, row in enumerate(data.entries[0].car):
            row.update(speed_kph=360 - index * 36, brake_on=True)
        response = analyze(data, AnalysisRequest(groups=["speed"]))
        self.assertAlmostEqual(
            metric(response, "specific_braking_energy_j_per_kg").value, 5000, places=5
        )
        self.assertAlmostEqual(
            metric(response, "max_deceleration_g").value, 10 / 9.80665, places=6
        )

    def test_clean_laps_theoretical_sectors_and_unfuelcorrected_tyre_slope(self):
        data = straight_data(360)
        data.entries[0].laps = [
            lap(number, 60000 + number * 100) for number in range(1, 6)
        ]
        dirty = lap(6, 50000)
        dirty["is_deleted"] = True
        data.entries[0].laps.append(dirty)
        response = analyze(data, AnalysisRequest(groups=["laps", "stints"]))
        self.assertEqual(metric(response, "clean_lap_count").value, 5)
        self.assertEqual(metric(response, "deleted_lap_count").value, 1)
        self.assertEqual(metric(response, "best_lap_ms").value, 60100)
        self.assertEqual(metric(response, "theoretical_best_lap_ms").value, 60100)
        self.assertAlmostEqual(
            metric(response, "tyre_degradation_ms_per_lap").value[0][
                "slope_ms_per_lap"
            ],
            100,
            places=5,
        )
        self.assertFalse(
            metric(response, "tyre_degradation_ms_per_lap").value[0]["fuel_corrected"]
        )
        # Pure engine receives a prepared window from its caller; repository handles request bounds.
        data.start_ms = 10000
        data.end_ms = 119000
        partial = analyze(data, AnalysisRequest(groups=["laps"]))
        self.assertEqual(metric(partial, "lap_count").value, 0)

    def test_braking_is_not_a_crash_but_nonpit_rapid_stop_is_a_candidate(self):
        data = straight_data(12)
        for row, speed in zip(
            data.entries[0].car,
            [300, 200, 100, 100, 200, 300, 300, 300, 300, 300, 300, 300],
        ):
            row["speed_kph"] = speed
        response = analyze(data, AnalysisRequest(groups=["incidents"]))
        self.assertGreater(metric(response, "rapid_speed_drop_count").value, 0)
        self.assertEqual(metric(response, "possible_incident_count").value, 0)
        for row, speed in zip(
            data.entries[0].car, [300, 200, 0, 0, 0, 0, 0, 0, 0, 100, 200, 300]
        ):
            row["speed_kph"] = speed
        response = analyze(data, AnalysisRequest(groups=["incidents"]))
        self.assertEqual(metric(response, "possible_incident_count").value, 1)
        event = next(
            event for event in response.events if event.kind == "possible_incident"
        )
        self.assertEqual(event.classification, "candidate")
        self.assertFalse(event.evidence["confirmed_crash"])
        data.entries[0].laps[0]["pit_in_time_ms"] = 1000
        self.assertEqual(
            metric(
                analyze(data, AnalysisRequest(groups=["incidents"])),
                "possible_incident_count",
            ).value,
            0,
        )
        data.entries[0].laps[0].pop("pit_in_time_ms")
        data.track_status = [dict(session_time_ms=0, status="5")]
        self.assertEqual(
            metric(
                analyze(data, AnalysisRequest(groups=["incidents"])),
                "possible_incident_count",
            ).value,
            0,
        )

    def test_event_kind_filter_preserves_metrics_and_keeps_later_candidates_visible(
        self,
    ):
        data = straight_data(12)
        for row, speed in zip(
            data.entries[0].car, [300, 200, 0, 0, 0, 0, 0, 0, 0, 100, 200, 300]
        ):
            row["speed_kph"] = speed
        response = analyze(
            data,
            AnalysisRequest(groups=["incidents"], event_kinds=["possible_incident"]),
        )
        self.assertEqual(response.total_event_count, 1)
        self.assertEqual(
            [event.kind for event in response.events], ["possible_incident"]
        )
        self.assertGreater(metric(response, "rapid_speed_drop_count").value, 0)
        with self.assertRaises(ValueError):
            AnalysisRequest(event_kinds=["confirmed_crash"])

    def test_missing_samples_spikes_and_stale_interpolation_are_not_motion(self):
        data = straight_data(60)
        data.entries[0].car = [
            dict(session_time_ms=0, speed_kph=300),
            dict(session_time_ms=10000, speed_kph=0),
        ]
        data.entries[0].positions = [
            dict(session_time_ms=0, x=1000, y=1000),
            dict(session_time_ms=1000, x=1000000, y=1000),
            dict(session_time_ms=2000, x=0, y=0),
        ]
        response = analyze(
            data, AnalysisRequest(groups=["quality", "speed", "position", "incidents"])
        )
        self.assertEqual(metric(response, "car_gap_count").value, 1)
        self.assertEqual(metric(response, "position_jump_count").value, 1)
        self.assertEqual(metric(response, "invalid_position_sample_count").value, 1)
        self.assertIsNone(metric(response, "integrated_distance_m").value)
        self.assertEqual(metric(response, "rapid_speed_drop_count").value, 0)
        self.assertTrue(
            np.isnan(
                aligned_values(
                    data.entries[0].car, "speed_kph", np.array([5000]), 2000
                )[0]
            )
        )

    def test_circle_reference_projection_and_offtrack_flag_are_distinct(self):
        data = straight_data(61)
        angles = np.linspace(0, 2 * np.pi, 361)
        points = np.column_stack(
            [200 + 100 * np.cos(angles), 200 + 100 * np.sin(angles)]
        )
        data.reference = ReferenceLine(points)
        distance, progress = data.reference.project(
            [[310, 200], [200, 300], [100, 200]]
        )
        self.assertAlmostEqual(distance[0], 10, places=3)
        self.assertAlmostEqual(progress[1], 25, places=3)
        self.assertAlmostEqual(progress[2], 50, places=3)
        self.assertAlmostEqual(data.reference.length, 2 * np.pi * 100, delta=0.02)
        data.entries[0].positions = [
            dict(
                session_time_ms=t * 1000,
                x=(200 + 100 * math.cos(t / 60 * 2 * math.pi)) * 10,
                y=(200 + 100 * math.sin(t / 60 * 2 * math.pi)) * 10,
                track_status="OnTrack",
            )
            for t in range(61)
        ]
        response = analyze(data, AnalysisRequest(groups=["position"]))
        self.assertLess(metric(response, "max_line_deviation_m").value, 0.01)
        self.assertEqual(metric(response, "reported_offtrack_time_s").value, 0)
        data.entries[0].positions[5]["track_status"] = "OffTrack"
        response = analyze(data, AnalysisRequest(groups=["position"]))
        self.assertEqual(metric(response, "reported_offtrack_time_s").value, 1)
        self.assertEqual(metric(response, "large_line_deviation_time_s").value, 0)

    def test_weather_circular_mean_source_conversion_and_flag_intervals(self):
        data = straight_data(120)
        data.weather = [
            dict(
                session_time_ms=t,
                wind_direction_deg=direction,
                wind_speed_kph=36,
                rainfall=rain,
                track_temp_c=30,
            )
            for t, direction, rain in [(0, 359, False), (60000, 1, True)]
        ]
        data.track_status = [
            dict(session_time_ms=0, status="1"),
            dict(session_time_ms=30000, status="4"),
            dict(session_time_ms=90000, status="1"),
        ]
        response = analyze(data, AnalysisRequest(groups=["conditions"]))
        self.assertAlmostEqual(
            metric(response, "mean_wind_direction_deg", None).value, 0, places=5
        )
        self.assertEqual(metric(response, "reported_rain_time_s", None).value, 60)
        self.assertEqual(metric(response, "safety_car_time_s", None).value, 60)
        self.assertEqual(metric(response, "clear_track_time_s", None).value, 60)
        bundle = source_bundle()
        bundle.weather = [dict(Time=timedelta(seconds=0), WindSpeed=10)]
        snapshot = NormalizationService().build_snapshot(bundle, ttl_hours=1)
        self.assertEqual(snapshot.weather_samples[0].wind_speed_kph, 36)

    def test_simultaneous_proximity_gear_steps_and_event_limits(self):
        data = straight_data(60)
        other = deepcopy(data.entries[0])
        other.id = "two"
        other.car_number = "2"
        for row in other.positions:
            row["y"] += 200
        data.entries.append(other)
        data.entries[0].car[0]["gear"] = 4
        data.entries[0].car[0]["drs_state"] = 8
        response = analyze(data, AnalysisRequest(groups=["racing", "powertrain"]))
        self.assertAlmostEqual(
            metric(response, "nearest_car_distance_m").value, 20, places=5
        )
        self.assertEqual(
            metric(response, "close_car_time_s").value, 60 - 1
        )  # interpolation ends at the final observed point
        self.assertEqual(metric(response, "observed_upshifts").value, 2)
        self.assertEqual(metric(response, "reported_drs_activations").value, 1)
        data.entries[0].positions[5]["track_status"] = "OffTrack"
        response = analyze(data, AnalysisRequest(groups=["position"], max_events=0))
        self.assertEqual(len(response.events), 0)
        self.assertTrue(response.events_truncated)
        self.assertGreater(response.total_event_count, 0)

    def test_empty_data_and_catalog_have_complete_serializable_implementations(self):
        response = analyze(
            AnalysisData("empty", 0, 60000, entries=[EntryData("one", "1")]),
            AnalysisRequest(),
        )
        self.assertEqual({row.metric_id for row in response.metrics}, set(DEFINITIONS))
        self.assertEqual(len(response.metrics), len(DEFINITIONS))
        self.assertEqual(metric(response, "mean_speed_kph").status, "unavailable")
        json.dumps(response.model_dump(mode="json"), allow_nan=False)
        with self.assertRaises(ValueError):
            analyze(straight_data(), AnalysisRequest(metric_ids=["made_up"]))

    def test_race_control_utc_uses_feed_origin_and_racing_number(self):
        bundle = source_bundle()
        origin = datetime(2025, 1, 1, 11, tzinfo=timezone.utc)
        bundle.metadata.actual_start_utc = origin + timedelta(hours=1)
        bundle.metadata.session_time_origin_utc = origin
        bundle.race_control_messages = [
            dict(
                Time=origin + timedelta(seconds=30),
                RacingNumber="1",
                Message="CAR 1 INCIDENT NOTED",
                Category="CarEvent",
            )
        ]
        snapshot = NormalizationService().build_snapshot(bundle, ttl_hours=1)
        self.assertEqual(len(snapshot.race_control_messages), 1)
        message = snapshot.race_control_messages[0]
        self.assertEqual(message.session_time_ms, 30000)
        self.assertEqual(message.driver_number, "1")
        self.assertEqual(message.source_entry_key, snapshot.entries[0].source_entry_key)
        self.assertEqual(message.source_time_utc, origin + timedelta(seconds=30))
        bundle.metadata.session_time_origin_utc = None
        self.assertEqual(
            NormalizationService()
            .build_snapshot(bundle, ttl_hours=1)
            .race_control_messages,
            [],
        )

    def test_events_keep_earliest_across_groups_and_coarse_sampling_has_bounded_gaps(
        self,
    ):
        request = AnalysisRequest(max_events=2, sample_interval_ms=5000)
        self.assertEqual(request.options.max_sample_gap_ms, 10000)
        result = Results(request)
        for start in (10000, 20000, 5000, 7000):
            result.event("sample", None, start, start, 1)
        self.assertEqual(
            sorted(event.start_time_ms for event in result.events), [5000, 7000]
        )
        self.assertEqual(result.total_events, 4)
        data = straight_data(12)
        data.race_control = [
            dict(session_time_ms=5000, driver_number="11", message="CAR 11 INCIDENT")
        ]
        response = analyze(data, AnalysisRequest(groups=["incidents"]))
        self.assertEqual(metric(response, "reported_incident_message_count").value, 0)
