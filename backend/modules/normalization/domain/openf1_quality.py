"""Deterministic OpenF1 lap qualification, not an assertion of FastF1 equivalence."""
from bisect import bisect_right
from datetime import timedelta
import math
import re

QUALITY_POLICY = "openf1_clean_lap_v1"


def finite_positive(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def derive_track_status(controls):
    phase, sectors, events = None, set(), []
    for row in sorted(controls, key=lambda v: v["SessionTime"]):
        message = (row.get("Message") or "").upper()
        flag, scope = row.get("Flag"), row.get("Scope")
        sector = row.get("Sector")
        if message.startswith(("VIRTUAL SAFETY CAR DEPLOYED", "VSC DEPLOYED")):
            phase = "6"
        elif message.startswith(("VIRTUAL SAFETY CAR ENDING", "VSC ENDING")):
            phase = "7"
        elif message.startswith(("SAFETY CAR DEPLOYED", "SC DEPLOYED")):
            phase = "4"
        elif flag == "RED" and scope == "Track":
            phase = "5"
        elif (flag in ("GREEN", "CLEAR") and scope == "Track") or message in ("TRACK CLEAR", "ALL CLEAR", "GREEN FLAG"):
            phase, sectors = "1", set()
        elif flag in ("YELLOW", "DOUBLE YELLOW"):
            sectors.add(sector if sector is not None else "unknown")
        elif flag == "CLEAR" and scope == "Sector":
            sectors.discard(sector)
        status = phase if phase in ("4", "5", "6", "7") else "2" if sectors else phase
        if status and (not events or events[-1]["Status"] != status):
            events.append({"SessionTime": row["SessionTime"], "Date": row.get("Date"), "Status": status, "Message": row.get("Message")})
    return events


def qualify_laps(laps, controls, pits):
    """Require sectors within 3 ms, contiguous clock within 750 ms, observed clear track,
    no pit/deletion, and no first lap after start or a neutralized lap. Unknown fails closed.
    """
    events = derive_track_status(controls)
    event_times = [row["SessionTime"] for row in events]
    by_driver = {}
    for row in laps:
        by_driver.setdefault(str(row["DriverNumber"]), []).append(row)
    pit_laps = {(str(row["driver_number"]), int(row["lap_number"])) for row in pits if row.get("lap_number") is not None}
    for car, rows in by_driver.items():
        rows.sort(key=lambda row: row["LapNumber"])
        for index, row in enumerate(rows):
            if row.get("OpenF1PitOutLap") or (index and row.get("Stint") is not None and rows[index-1].get("Stint") is not None and row["Stint"] != rows[index-1]["Stint"]):
                pit_laps.add((car, row["LapNumber"]))
    quality = []
    for car, rows in by_driver.items():
        rows.sort(key=lambda row: row["LapNumber"])
        for index, row in enumerate(rows):
            reasons = []
            start, end, duration = row.get("LapStartTime"), row.get("Time"), row.get("LapTime")
            number = row["LapNumber"]
            if duration is None or not 10 < duration.total_seconds() < 600:
                reasons.append("missing_or_invalid_lap_duration")
            sectors = [row.get(f"Sector{n}Time") for n in (1,2,3)]
            if not all(value is not None and finite_positive(value.total_seconds()) for value in sectors):
                reasons.append("missing_sector_duration")
            elif duration is None or abs(sum(v.total_seconds() for v in sectors)-duration.total_seconds()) > .003001:
                reasons.append("sector_sum_mismatch")
            previous = rows[index-1] if index else None
            following = rows[index+1] if index+1 < len(rows) else None
            neighbours = []
            if previous and previous["LapNumber"] == number-1 and previous.get("Time") is not None and start is not None:
                neighbours.append(abs((start-previous["Time"]).total_seconds()) <= .75)
            if following and following["LapNumber"] == number+1 and following.get("LapStartTime") is not None and end is not None:
                neighbours.append(abs((following["LapStartTime"]-end).total_seconds()) <= .75)
            if not neighbours or not all(neighbours):
                reasons.append("unverified_clock_continuity")
            statuses = set()
            if start is not None and end is not None:
                lower, upper = start-timedelta(seconds=1), end+timedelta(seconds=1)
                at = bisect_right(event_times, lower)-1
                if at >= 0:
                    statuses.add(events[at]["Status"])
                else:
                    reasons.append("unknown_start_track_status")
                statuses.update(v["Status"] for v in events[max(0, at+1):] if v["SessionTime"] <= upper)
            if statuses != {"1"}:
                reasons.append("track_not_confirmed_clear")
            row["TrackStatus"] = "".join(sorted(statuses)) or None
            if number == 1 or (previous and previous.get("TrackStatus") != "1"):
                reasons.append("start_or_post_neutralization_lap")
            if row.pop("OpenF1PitOutLap", False) or any((car,n) in pit_laps for n in (number-1,number,number+1)):
                reasons.append("pit_or_adjacent_pit_lap")
            # The race-control lap field is used only with an explicit driver. Where
            # available, match the published deleted duration rather than guessing a lap.
            deleted = False
            for message in controls:
                text = (message.get("Message") or "").upper()
                if "DELETED" not in text and "REINSTATED" not in text:
                    continue
                driver = str(message.get("RacingNumber") or "")
                if driver != car and not re.search(r"\bCAR\s+" + re.escape(car) + r"\b", text):
                    continue
                duration_match = re.search(r"\b(\d+):(\d{2})\.(\d{3})\b", text)
                if duration_match and duration is not None:
                    seconds = int(duration_match[1])*60+int(duration_match[2])+int(duration_match[3])/1000
                    matches = abs(duration.total_seconds()-seconds) <= .001001
                else:
                    matches = message.get("Lap") == number
                if matches:
                    deleted = "REINSTATED" not in text
                    row["DeletedReason"] = message.get("Message") if deleted else None
            row["Deleted"] = deleted
            if deleted:
                reasons.append("deleted_lap")
            row["IsAccurate"] = not reasons
            quality.append({"driver_number": car, "lap_number": number, "clean": not reasons,
                            "reasons": reasons, "policy": QUALITY_POLICY})
    return events, quality
