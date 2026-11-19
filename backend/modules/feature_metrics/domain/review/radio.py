"""Time the published radio archive independently from causal race observations."""

from collections import Counter
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit

from .observations import radio_messages


_ARCHIVE_FILENAME = re.compile(r"[A-Z0-9]+_(\d{1,2})_(\d{8}_\d{6})\.mp3", re.I)
_MAX_OFFSET_MS = 14 * 3_600_000
_OFFSET_STEP_MS = 15 * 60_000
_MAX_ESTIMATED_FEED_DELAY_MS = 120_000


def _venue_offset_ms(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"([+-]?)(\d{2}):([0-5]\d):00", value)
    if match is None:
        return None
    sign, hours, minutes = match.groups()
    offset = (60 * int(hours) + int(minutes)) * 60_000
    if offset > _MAX_OFFSET_MS:
        return None
    return -offset if sign == "-" else offset


def _archive_wall_time_ms(clip, origin, cars):
    path = urlsplit(clip["recording_url"]).path
    if "/TeamRadio/" not in path:
        return None
    match = _ARCHIVE_FILENAME.fullmatch(path.rsplit("/", 1)[-1])
    if match is None or str(int(match[1])) != cars[clip["entry_id"]]:
        return None
    try:
        wall_time = datetime.strptime(match[2], "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        return round((wall_time - origin).total_seconds() * 1000)
    except ValueError:
        return None


def _plausible_delay(feed, recorded):
    return 0 <= feed - recorded <= _MAX_ESTIMATED_FEED_DELAY_MS


def _infer_venue_offset(samples):
    """Legacy imports can estimate an offset from agreement across several clips."""
    votes = Counter()
    parsed = 0
    for feed, wall in samples:
        if wall is None:
            continue
        parsed += 1
        offset = round((wall - feed) / _OFFSET_STEP_MS) * _OFFSET_STEP_MS
        if abs(offset) <= _MAX_OFFSET_MS and _plausible_delay(feed, wall - offset):
            votes[offset] += 1
    if votes:
        offset, count = votes.most_common(1)[0]
        if count >= 3 and count * 4 >= parsed * 3:
            return offset
    return None


def radio_archive(details, origin, driver_ids):
    available = (
        "team_radio" in details
        and "team_radio" not in details.get("unavailable_sources", [])
        and origin is not None
    )
    if not available:
        return {"available": False, "clips": []}

    clips = radio_messages(details, origin, driver_ids, float("inf"))
    cars = {entry: car for car, entry in driver_ids.items()}
    samples = [(clip["time_ms"], _archive_wall_time_ms(clip, origin, cars)) for clip in clips]
    offset = _venue_offset_ms(details.get("session_gmt_offset"))
    if offset is None:
        offset = _infer_venue_offset(samples)

    timeline = []
    for clip, (feed, wall) in zip(clips, samples):
        recorded = wall - offset if wall is not None and offset is not None else -1
        estimated = recorded >= 0 and _plausible_delay(feed, recorded)
        timeline.append({
            "entry_id": clip["entry_id"],
            "recording_url": clip["recording_url"],
            "time_ms": recorded if estimated else feed,
            "feed_time_ms": feed,
            "timing_basis": "estimated_recording" if estimated else "source_feed",
        })
    return {"available": True, "clips": sorted(timeline, key=lambda clip: -clip["time_ms"])}
