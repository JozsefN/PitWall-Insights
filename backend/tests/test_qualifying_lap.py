import math
import unittest

from modules.feature_metrics.domain.review.qualifying_lap import eligible_lap, qualifying_splits


def timed_lap(driver, number, time, first_sector):
    duration = time
    return {
        "id": f"{driver}:{number}", "session_entry_id": driver, "lap_number": number,
        "lap_time_ms": duration, "lap_start_time_ms": 0, "lap_end_time_ms": duration,
        "sector_1_time_ms": first_sector, "sector_2_time_ms": 27000,
        "sector_3_time_ms": duration - first_sector - 27000,
    }


def positions(lap):
    return [
        {"x": 9100 * math.cos(i / 220 * math.tau), "y": 7000 * math.sin(i / 220 * math.tau),
         "session_time_ms": round(i * lap["lap_time_ms"] / 220)}
        for i in range(221)
    ]


class QualifyingLapTests(unittest.TestCase):
    def test_each_split_ranks_the_whole_field_and_compares_the_viewed_lap(self):
        laps = [timed_lap(f"driver{i}", 2, 75_000 + 170 * i, 24_000 + 55 * i) for i in range(22)]
        earlier = timed_lap("driver5", 1, 78_000, 24_500)
        laps.append(earlier)
        data = qualifying_splits(laps, earlier, {lap["id"]: positions(lap) for lap in laps}, include_minisectors=True)
        self.assertEqual(data["minisector_driver_count"], 22)
        self.assertTrue(data["focus_minisectors_available"])
        self.assertEqual(len(data["minisectors"]), 20)
        self.assertTrue(all(len(row["ranking"]) == 22 for row in data["minisectors"]))
        self.assertEqual(sum(row["focus_ms"] for row in data["minisectors"]), earlier["lap_time_ms"])
        self.assertEqual(data["sectors"][0]["colour"], "yellow")
        self.assertEqual(data["sectors"][0]["focus_delta_ms"], 500)
        self.assertEqual(data["sectors"][0]["ranking"][0]["delta_to_focus_ms"], -500)
        self.assertEqual(data["sectors"][0]["path"][-1], data["sectors"][1]["path"][0])
        self.assertEqual(data["minisectors"][0]["path"][-1], data["minisectors"][1]["path"][0])

    def test_official_splits_work_with_missing_positions_and_only_eligible_laps(self):
        best, second = timed_lap("a", 1, 75_000, 24_000), timed_lap("b", 1, 75_500, 24_500)
        self.assertTrue(eligible_lap(best))
        self.assertFalse(eligible_lap({**best, "is_deleted": True}))
        self.assertFalse(eligible_lap({**best, "pit_out_time_ms": 3}))
        self.assertFalse(eligible_lap({**best, "is_generated": True}))
        data = qualifying_splits([best, second], best, {}, include_minisectors=True)
        self.assertEqual(data["sectors"][0]["colour"], "purple")
        self.assertEqual(len(data["sectors"][0]["ranking"]), 2)
        self.assertEqual(data["minisector_driver_count"], 0)
        self.assertEqual(data["minisectors"][0]["colour"], "unknown")
        self.assertEqual(data["minisectors"][0]["ranking"], [])
        personal = qualifying_splits([best, second], second, {}, include_minisectors=False)
        self.assertEqual(personal["sectors"][0]["colour"], "green")
