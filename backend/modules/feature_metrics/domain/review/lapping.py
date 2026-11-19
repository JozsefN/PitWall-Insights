"""Constant-pace catch scenarios for reported lapped cars at a shared track phase."""

import math

from ..race_estimation.common import finite


def lapped_traffic(data, field, paces, cutoff, horizon):
    reference = data.reference
    if reference is None:
        return []
    positions = {}
    for entry in data.entries:
        if entry.positions:
            row = entry.positions[-1]
            if 0 <= cutoff - row["session_time_ms"] <= 1200 and all(
                finite(row.get(key)) for key in ("x", "y")
            ):
                deviation, progress = reference.project(
                    [[row["x"] * 0.1, row["y"] * 0.1]]
                )
                if deviation[0] <= 30:
                    positions[entry.id] = (
                        float(progress[0]) / 100,
                        row["session_time_ms"],
                    )
    speeds = {
        row["entry_id"]: 1 / row["median_pace_s"]
        for row in paces
        if row["samples"] >= 3
    }
    lapped = [row["entry_id"] for row in field if row.get("laps_down_reported", 0) > 0]
    output = []
    for row in field:
        follower = row["entry_id"]
        if (
            row.get("laps_down_reported")
            or follower not in positions
            or follower not in speeds
        ):
            continue
        for ahead in lapped:
            if (
                ahead not in positions
                or ahead not in speeds
                or speeds[ahead] >= speeds[follower]
                or abs(positions[follower][1] - positions[ahead][1]) > 800
            ):
                continue
            gap = (positions[ahead][0] - positions[follower][0]) % 1
            catch_s = gap / (speeds[follower] - speeds[ahead])
            if not 0 < catch_s <= horizon / speeds[follower]:
                continue
            progress = (positions[follower][0] + speeds[follower] * catch_s) % 1
            segment_index = (
                int((reference.arcs <= progress * reference.length).sum()) - 1
            )
            first = reference.vectors[(segment_index - 2) % len(reference.vectors)]
            last = reference.vectors[(segment_index + 2) % len(reference.vectors)]
            turn = abs(
                math.atan2(first[0] * last[1] - first[1] * last[0], first @ last)
            )
            corner = turn >= math.radians(12)
            output.append(
                {
                    "entry_id": follower,
                    "lapped_entry_id": ahead,
                    "catch_after_s": catch_s,
                    "catch_after_laps": catch_s * speeds[follower],
                    "progress_pct": progress * 100,
                    "reference_shape": "turn" if corner else "straight_like",
                    "delay_sensitivity_s": [0, 1.0 if corner else 0.25],
                    "method": "Constant mean lap progress. Delay range is an illustrative scenario.",
                }
            )
    return sorted(output, key=lambda row: row["catch_after_s"])[:60]
