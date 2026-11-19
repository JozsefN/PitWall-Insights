from copy import deepcopy
from datetime import timedelta
import unittest
from modules.normalization.domain.openf1_quality import qualify_laps


def laps():
    return [{"DriverNumber":"1","LapNumber":n,"LapStartTime":timedelta(seconds=(n-1)*60),
             "Time":timedelta(seconds=n*60),"LapTime":timedelta(seconds=60),
             **{f"Sector{i}Time":timedelta(seconds=20) for i in (1,2,3)}} for n in range(1,5)]


def green():
    return [{"SessionTime":timedelta(seconds=-10),"Flag":"GREEN","Scope":"Track","Message":"GREEN FLAG"}]


class OpenF1QualityTests(unittest.TestCase):
    def test_clean_laps_are_usable_by_existing_strategy_filter(self):
        from modules.feature_metrics.domain.strategy.common import clean_laps
        from types import SimpleNamespace
        rows = laps()
        events, quality = qualify_laps(rows, green(), [])
        self.assertEqual([v["lap_number"] for v in quality if v["clean"]], [2,3,4])
        canonical = [{"lap_number":v["LapNumber"],"lap_start_time_ms":v["LapStartTime"].total_seconds()*1000,
                      "lap_end_time_ms":v["Time"].total_seconds()*1000,"lap_time_ms":60000,
                      "is_accurate":v["IsAccurate"],"track_status":v["TrackStatus"]} for v in rows]
        self.assertEqual(len(clean_laps(SimpleNamespace(laps=canonical),240000)),3)

    def test_unknown_flags_sectors_and_clock_continuity_fail_closed(self):
        rows = laps()
        _, quality = qualify_laps(rows, [], [])
        self.assertFalse(any(v["clean"] for v in quality))
        rows = laps()
        rows[1]["Sector1Time"] = timedelta(seconds=21)
        rows[2]["LapStartTime"] += timedelta(seconds=2)
        _, quality = qualify_laps(rows, green(), [])
        self.assertIn("sector_sum_mismatch", quality[1]["reasons"])
        self.assertIn("unverified_clock_continuity", quality[2]["reasons"])

    def test_safety_car_and_first_lap_after_neutralization_are_excluded(self):
        rows = laps()
        controls = green()+[{"SessionTime":timedelta(seconds=80),"Message":"SAFETY CAR DEPLOYED"},
                            {"SessionTime":timedelta(seconds=115),"Message":"GREEN FLAG","Flag":"GREEN","Scope":"Track"}]
        _, quality = qualify_laps(rows, controls, [])
        self.assertFalse(quality[1]["clean"])
        self.assertFalse(quality[2]["clean"])
        self.assertTrue(quality[3]["clean"])

    def test_sector_clear_does_not_clear_an_active_safety_car(self):
        rows = laps()
        controls = green()+[{"SessionTime":timedelta(seconds=65),"Message":"SAFETY CAR DEPLOYED"},
                            {"SessionTime":timedelta(seconds=70),"Flag":"CLEAR","Scope":"Sector","Sector":1}]
        events, quality = qualify_laps(rows, controls, [])
        self.assertEqual(events[-1]["Status"],"4")
        self.assertFalse(quality[-1]["clean"])

    def test_pit_lap_and_adjacent_laps_are_excluded_without_inventing_entry_timestamps(self):
        rows = laps()
        _, quality = qualify_laps(rows, green(), [{"driver_number":1,"lap_number":3}])
        self.assertFalse(any(v["clean"] for v in quality))
        self.assertNotIn("PitInTime",rows[2])

    def test_deleted_laps_remain_excluded(self):
        rows = laps()
        controls = green()+[{"SessionTime":timedelta(seconds=125),"Message":"CAR 1 LAP TIME DELETED","Lap":2,"RacingNumber":"1"}]
        _, quality = qualify_laps(rows, controls, [])
        self.assertTrue(rows[1]["Deleted"])
        self.assertFalse(quality[1]["clean"])
        self.assertTrue(quality[2]["clean"])

    def test_stint_change_excludes_surrounding_pit_laps_even_without_pit_report(self):
        rows=laps()
        for row in rows:
            row["Stint"]=1 if row["LapNumber"]<3 else 2
        _, quality=qualify_laps(rows,green(),[])
        self.assertFalse(any(v["clean"] for v in quality))

    def test_neutralization_at_boundary_is_conservatively_included(self):
        rows = laps()
        controls = green()+[{"SessionTime":timedelta(seconds=120.5),"Message":"VIRTUAL SAFETY CAR DEPLOYED"}]
        _, quality = qualify_laps(rows, controls, [])
        self.assertFalse(quality[1]["clean"])
