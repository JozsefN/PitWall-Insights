from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from modules.feature_metrics.domain.review.timing_tower import (
    flag_series,
    gap_ms,
    lap_validity_reports,
    timed_lap,
    timing_series,
)


class TimingTowerTests(unittest.TestCase):
    def test_interval_keeps_reported_seconds_and_lap_units(self):
        self.assertEqual(gap_ms(1.823), 1823)
        self.assertEqual(gap_ms("+2 LAPS"), -2)
        self.assertIsNone(gap_ms(float("nan")))
        self.assertIsNone(gap_ms(True))
        self.assertIsNone(gap_ms("PIT"))

    def test_series_orders_by_canonical_time_and_ignores_other_drivers(self):
        origin = datetime(2025, 4, 13, 15, 0, tzinfo=timezone.utc)
        first, second = "2025-04-13T15:00:03Z", "2025-04-13T15:00:04+00:00"
        ranks, gaps = timing_series(
            {
                "race_positions": [
                    {"date": second, "driver_number": 4, "position": 1},
                    {"date": first, "driver_number": 4, "position": 1},
                    {"date": first, "driver_number": 99, "position": 2},
                ],
                "intervals": [
                    {
                        "date": second,
                        "driver_number": 4,
                        "gap_to_leader": 0,
                        "interval": None,
                    }
                ],
            },
            origin,
            {"4", "16"},
        )
        self.assertEqual(ranks, {"4": [[3000, 1]]})
        self.assertEqual(gaps, {"4": [[4000, 0, None]]})

    def test_sector_flags_remain_local_and_clear_again(self):
        def control(time, flag, scope, sector=None, message=""):
            return dict(
                session_time_ms=time,
                flag=flag,
                scope=scope,
                sector=sector,
                message=message,
            )

        flags = flag_series(
            [
                dict(session_time_ms=31, status="4"),
                dict(session_time_ms=40, status="1"),
            ],
            [
                control(1, "GREEN", "Track"),
                control(10, "YELLOW", "Sector", 4),
                control(11, "DOUBLE YELLOW", "Sector", 5),
                control(20, "CLEAR", "Sector", 4),
                control(40, None, None, message="TRACK CLEAR"),
                control(60, None, None, message="CHEQUERED FLAG"),
            ],
        )
        self.assertEqual(
            flags,
            [
                [1, "GREEN", []],
                [10, "LOCAL YELLOW", [4]],
                [11, "LOCAL DOUBLE YELLOW", [4, 5]],
                [20, "LOCAL DOUBLE YELLOW", [5]],
                [31, "SAFETY CAR", [5]],
                [40, "GREEN", []],
                [60, "CHEQUERED", []],
            ],
        )

    def test_timed_lap_carries_report_dates_and_ignores_untraceable_exclusions(self):
        def message(time, text):
            return dict(
                session_time_ms=time, message=text, driver_number=None, lap_number=3
            )

        reports = lap_validity_reports(
            [
                message(83_000, "CAR 4 LAP TIME 1:20.000 DELETED"),
                message(90_000, "CAR 4 LAP TIME 1:20.000 REINSTATED"),
            ]
        )
        row = SimpleNamespace(
            lap_end_time_ms=82_000,
            lap_time_ms=80_000,
            pit_in_time_ms=None,
            pit_out_time_ms=None,
            lap_number=3,
            is_deleted=False,
        )
        self.assertEqual(
            timed_lap(row, reports["4"]),
            [82_000, 80_000, [[83_000, False], [90_000, True]]],
        )
        row.is_deleted = True
        self.assertIsNone(timed_lap(row, ()))
