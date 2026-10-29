from datetime import datetime, timedelta, timezone
import unittest
import numpy as np
from modules.feature_metrics.infrastructure.openf1_context import normalize_pit_reports
from modules.feature_metrics.domain.strategy.georegistration import (
    align_metric_landmarks,
)
from modules.feature_metrics.domain.strategy.history import collect_incident_history
from modules.feature_metrics.domain.analysis.geometry import ReferenceLine
from test_strategy_math import data_fixture


class StrategyEnrichmentTests(unittest.TestCase):
    def test_reference_transit_uses_local_timing_and_wraps_the_finish(self):
        fraction = np.linspace(0, 1, 101)
        points = np.column_stack(
            [
                200 + 100 * np.cos(2 * np.pi * fraction),
                200 + 100 * np.sin(2 * np.pi * fraction),
            ]
        )
        line = ReferenceLine(
            points, sample_times_ms=100000 * np.sqrt(fraction), lap_duration_ms=100000
        )
        expected = 100 * (np.sqrt(0.75) - np.sqrt(0.25))
        self.assertAlmostEqual(line.forward_time_s(25, 75), expected, places=5)
        self.assertAlmostEqual(line.forward_time_s(75, 25), 100 - expected, places=5)
        self.assertIsNone(ReferenceLine(points).forward_time_s(25, 75))

    def test_openf1_lane_and_service_are_distinct_and_not_visible_immediately(self):
        origin = datetime(2025, 1, 1, tzinfo=timezone.utc)
        rows = [
            dict(
                session_key=123,
                driver_number=1,
                lap_number=5,
                date=(origin + timedelta(seconds=100)).isoformat(),
                lane_duration=22.5,
                stop_duration=2.5,
            )
        ]
        report = normalize_pit_reports(
            rows, entries_by_car={"1": "a"}, clock_origin=origin, session_key=123
        )[0]
        self.assertEqual(report.lane_duration_s, 22.5)
        self.assertEqual(report.stationary_duration_s, 2.5)
        self.assertEqual(report.event_time_ms, 100000)
        self.assertEqual(report.known_at_ms, 137500)
        with self.assertRaises(ValueError):
            normalize_pit_reports(
                rows, entries_by_car={"2": "b"}, clock_origin=origin, session_key=123
            )
        with self.assertRaises(ValueError):
            normalize_pit_reports(
                rows, entries_by_car={"1": "a"}, clock_origin=origin, session_key=456
            )
        rows[0]["stop_duration"] = None
        self.assertIsNone(
            normalize_pit_reports(
                rows, entries_by_car={"1": "a"}, clock_origin=origin, session_key=123
            )[0].stationary_duration_s
        )

    def test_landmark_registration_recovers_north_and_rejects_wrong_units(self):
        xy = np.array([[0, 0], [1000, 0], [1000, 1000], [0, 1000]], dtype=float)
        angle = np.deg2rad(30)
        rotation = np.array(
            [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
        )
        enu = xy @ rotation.T + np.array([100, 200])
        fitted = align_metric_landmarks(xy, enu)
        self.assertAlmostEqual(fitted["north_angle_xy_deg"], 60, places=6)
        self.assertAlmostEqual(fitted["scale"], 1, places=6)
        self.assertLess(fitted["residual_rmse_m"], 1e-6)
        with self.assertRaises(ValueError):
            align_metric_landmarks(xy * 10, enu)
        with self.assertRaises(ValueError):
            align_metric_landmarks([[0, 0], [1, 0], [2, 0]], [[0, 0], [1, 0], [2, 0]])
        broken = enu.copy()
        broken[-1] += [100, 100]
        with self.assertRaises(ValueError):
            align_metric_landmarks(xy, broken)

    def test_historical_labels_are_censored_deduplicated_and_horizon_specific(self):
        data = data_fixture(300000)
        # One stopped car from 130 to 150 seconds, then SC at 170 seconds.
        for row in data.entries[0].car:
            if 130000 <= row["session_time_ms"] <= 150000:
                row["speed_kph"] = 0
        data.track_status.append(dict(session_time_ms=170000, status="4"))
        labels = collect_incident_history(
            data,
            circuit_key="test",
            clock_origin=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        self.assertEqual({row.elapsed_stop_bin for row in labels}, {"4_10", "10_30"})
        self.assertTrue(all(row.outcome == "sc" for row in labels))
        self.assertEqual(len({row.incident_id for row in labels}), 1)
        # An incident too close to the end cannot be labelled "no SC" merely because the data ends.
        for row in data.entries[0].car:
            row["speed_kph"] = 0 if row["session_time_ms"] >= 280000 else 360
        data.track_status = [dict(session_time_ms=0, status="1")]
        self.assertEqual(
            collect_incident_history(
                data,
                circuit_key="test",
                clock_origin=datetime(2025, 1, 1, tzinfo=timezone.utc),
            ),
            [],
        )
