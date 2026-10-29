"""Conservative incident candidates; speed changes alone never prove a crash."""

import re
import numpy as np
from .common import car_arrays, episodes, pit_mask, neutralized_mask, stat


def driver_messages(entry, data):
    return [
        row
        for row in data.race_control
        if data.start_ms <= row["session_time_ms"] <= data.end_ms
        and (
            row.get("session_entry_id") == entry.id
            or str(row.get("driver_number") or "") == entry.car_number
        )
    ]


def calculate_incidents(data, request, result):
    for entry in data.entries:
        messages = driver_messages(entry, data)
        incident_messages = [
            row
            for row in messages
            if re.search(
                r"incident|collision|spun|spin|stopped|crash",
                row.get("message", ""),
                re.I,
            )
        ]
        track_messages = [
            row
            for row in messages
            if re.search(
                r"track limits|leaving the track", row.get("message", ""), re.I
            )
        ]
        result.put(
            "reported_incident_message_count",
            len(incident_messages),
            entry.id,
            n=len(data.race_control),
        )
        result.put(
            "reported_track_limit_message_count",
            len(track_messages),
            entry.id,
            n=len(data.race_control),
        )
        for row in incident_messages + track_messages:
            result.event(
                "race_control_driver_message",
                entry.id,
                row["session_time_ms"],
                row["session_time_ms"],
                1,
                "reported",
                message=row["message"],
                source_message_id=row.get("id"),
            )
        keys = (
            "rapid_speed_drop_count",
            "max_rapid_speed_drop_kph",
            "non_pit_stop_episode_count",
            "non_pit_stop_time_s",
            "possible_incident_count",
        )
        if not entry.car:
            for key in keys:
                result.put(
                    key, None, entry.id, warnings=["Car telemetry is not materialized."]
                )
            continue
        times, duration, speed, _, _ = car_arrays(entry, data, request)
        n = int(np.sum(np.isfinite(speed)))
        # A rolling high-speed point is valid only inside a continuous, finite run.
        drops = []
        run_start = 0
        for index in range(len(times)):
            if not np.isfinite(speed[index]):
                run_start = index + 1
                continue
            if index and (
                times[index] - times[index - 1] > request.options.max_sample_gap_ms
                or not np.isfinite(speed[index - 1])
            ):
                run_start = index
            left = max(
                run_start,
                int(
                    np.searchsorted(
                        times, times[index] - request.options.rapid_drop_window_ms
                    )
                ),
            )
            if left >= index:
                continue
            peak = left + int(np.argmax(speed[left:index]))
            drop = speed[peak] - speed[index]
            if drop >= request.options.rapid_drop_kph:
                # Merge overlapping detections of the same slowdown.
                if drops and times[peak] <= drops[-1]["end"]:
                    drops[-1]["end"] = times[index]
                    drops[-1]["drop"] = max(drops[-1]["drop"], float(drop))
                else:
                    drops.append(
                        {"start": times[peak], "end": times[index], "drop": float(drop)}
                    )
        excluded = pit_mask(entry, times) | neutralized_mask(data, times)
        stops = [
            (start, end, length)
            for start, end, length in episodes(
                (speed <= request.options.stopped_speed_kph) & ~excluded,
                times,
                duration,
            )
            if length * 1000 >= request.options.stopped_min_ms
        ]
        candidates = 0
        for drop in drops:
            result.event(
                "rapid_speed_drop",
                entry.id,
                drop["start"],
                drop["end"],
                0.8,
                drop_kph=drop["drop"],
                ordinary_braking_possible=True,
            )
        for start, end, length in stops:
            stop_start, stop_end = (
                times[start],
                times[end - 1] + duration[end - 1] * 1000,
            )
            result.event(
                "non_pit_stop", entry.id, stop_start, stop_end, 0.65, duration_s=length
            )
            related = [
                drop
                for drop in drops
                if stop_start - 5000 <= drop["end"] <= stop_start + 1000
            ]
            if not related:
                continue
            candidates += 1
            corroboration = [
                row
                for row in incident_messages
                if stop_start - 10000 <= row["session_time_ms"] <= stop_end + 10000
            ]
            result.event(
                "possible_incident",
                entry.id,
                min(drop["start"] for drop in related),
                stop_end,
                0.7 if corroboration else 0.45,
                "candidate",
                max_drop_kph=max(drop["drop"] for drop in related),
                stopped_duration_s=length,
                driver_message_count=len(corroboration),
                confirmed_crash=False,
            )
        confidence = min(
            0.8,
            float(np.sum(duration[np.isfinite(speed)]))
            / max(1, (data.end_ms - data.start_ms) / 1000),
        )
        for key, value in (
            ("rapid_speed_drop_count", len(drops)),
            ("max_rapid_speed_drop_kph", stat([d["drop"] for d in drops], "max")),
            ("non_pit_stop_episode_count", len(stops)),
            ("non_pit_stop_time_s", sum(s[2] for s in stops)),
            ("possible_incident_count", candidates),
        ):
            result.put(
                key,
                value if n else None,
                entry.id,
                n=n,
                confidence=(
                    min(confidence, 0.5)
                    if key == "possible_incident_count"
                    else confidence
                ),
                warnings=(
                    ["Heuristic candidate, never proof of a crash."]
                    if key == "possible_incident_count"
                    else []
                ),
            )
