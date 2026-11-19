import unittest

from scipy.spatial import cKDTree

from modules.session_domain.domain.pit_map import (
    PitFix, PitReport, PitTraceWindow, build_pit_map, pit_position_windows,
)


def pass_fixes(start: int, y: float = 200, stopped: bool = True) -> list[PitFix]:
    fixes = []
    for elapsed in range(-2500, 22501, 250):
        moving_time = elapsed
        if stopped:
            moving_time -= min(max(0, elapsed - 7000), 2000)
        fixes.append(PitFix(start + elapsed, (1000 + moving_time * 0.16, y)))
    return fixes


class PitMapTest(unittest.TestCase):
    def test_both_crossing_times_can_map_a_single_observed_drive_through(self):
        hint = PitTraceWindow("a", "team", 8, 10_000, 30_000, timed_crossings=True)
        result = build_pit_map([], {"a": pass_fixes(10_000, stopped=False)}, hints=[hint])
        self.assertGreater(len(result["lane"]), 20)
        self.assertEqual(result["visits"][0]["start_ms"], 10_000)
        self.assertEqual(result["visits"][0]["end_ms"], 30_000)
        self.assertEqual(result["boxes"], [])

    def test_repeated_observed_entries_and_exits_map_the_lane_without_reports(self):
        racing_line = cKDTree([(x, 0) for x in range(0, 6000, 20)])
        windows = [PitTraceWindow("a", "one", 1, 7_500, 32_500),
                   PitTraceWindow("b", "two", 2, 37_500, 62_500)]

        def traversal(start, offset):
            return [PitFix(fix.time_ms, (
                fix.point[0],
                min(1, max(0, (fix.time_ms - start) / 1500), max(0, (start + 20_000 - fix.time_ms) / 1500)) * offset,
            )) for fix in pass_fixes(start, stopped=False)]

        first, second = traversal(10_000, 150), traversal(40_000, 158)
        fixes = {"a": first, "b": second}
        result = build_pit_map([], fixes, hints=windows + [windows[0]], racing_line=racing_line)
        self.assertEqual(len(result["visits"]), 2)
        self.assertGreater(len(result["lane"]), 20)
        self.assertLess(result["lane"][0][1], 95)
        self.assertLess(result["lane"][-1][1], 95)
        for incomplete in ([], [fix for fix in second if fix.time_ms < 58_000],
                           [fix for fix in second if not 48_000 <= fix.time_ms <= 51_000]):
            with self.subTest(samples=len(incomplete)):
                result = build_pit_map([], {"a": first, "b": incomplete}, hints=windows, racing_line=racing_line)
                self.assertEqual(result["lane"], [])

    def test_overlapping_sample_windows_merge_only_for_the_same_driver(self):
        reports = [
            PitReport("a", "team", 6, 40000, 10000, None),
            PitReport("a", "team", 2, 6000, 5000, None),
            PitReport("b", "team", 7, 40000, 10000, None),
            PitReport("a", "team", 7, 51000, 5000, None),
            PitReport("a", "team", 8, 43500, 5000, None),
        ]
        self.assertEqual(pit_position_windows(reports), [
            ("a", 0, 13500), ("a", 27500, 58500), ("b", 27500, 52500),
        ])

    def test_pit_out_and_pit_in_stamps_find_the_same_lane_and_team_box(self):
        first = PitReport("a", "team", 12, 30000, 20000, None)
        second = PitReport("b", "team", 15, 40000, 20000, None)
        result = build_pit_map([first, second], {"a": pass_fixes(10000), "b": pass_fixes(40000, 204)})
        self.assertEqual([(row["start_ms"], row["end_ms"]) for row in result["visits"]], [(10000, 30000), (40000, 60000)])
        self.assertEqual(result["visits"][0]["stopped_from_ms"], 17000)
        self.assertEqual(result["visits"][0]["stopped_until_ms"], 19000)
        self.assertEqual(result["boxes"], [{"team_id": "team", "point": (2120.0, 202.0), "known_at_ms": 60000}])
        self.assertLess(result["lane"][0][0], 1000)
        self.assertGreater(result["lane"][-1][0], 3800)

    def test_drive_through_uses_the_lane_without_inventing_a_stop(self):
        service = PitReport("a", "team", 12, 30000, 20000, 2)
        drive_through = PitReport("b", "other", 15, 60000, 20000, None)
        result = build_pit_map([service, drive_through], {"a": pass_fixes(10000), "b": pass_fixes(40000, stopped=False)})
        self.assertEqual(len(result["visits"]), 2)
        self.assertIsNone(result["visits"][1]["stopped_from_ms"])
        self.assertEqual([box["team_id"] for box in result["boxes"]], ["team"])

    def test_gap_does_not_create_a_bridge_or_a_box(self):
        report = PitReport("a", "team", 12, 30000, 20000, 2)
        fixes = [fix for fix in pass_fixes(10000) if not 16000 <= fix.time_ms <= 20000]
        self.assertEqual(build_pit_map([report], {"a": fixes}), {"lane": [], "boxes": [], "visits": []})

    def test_two_independent_passes_map_a_lane_even_without_stationary_samples(self):
        first = PitReport("a", "one", 12, 30000, 20000, None)
        second = PitReport("b", "two", 15, 60000, 20000, None)
        fixes = {"a": pass_fixes(10000, stopped=False), "b": pass_fixes(40000, 204, stopped=False)}
        result = build_pit_map([first, second], fixes)
        self.assertGreater(len(result["lane"]), 20)
        self.assertEqual(len(result["visits"]), 2)
        self.assertEqual(result["boxes"], [])
        self.assertEqual(build_pit_map([first], fixes)["lane"], [])


if __name__ == "__main__":
    unittest.main()
