"""Map optional source reports into strategy context without coupling ingestion to feature models."""

from datetime import datetime
import math
from modules.feature_metrics.domain.strategy.models import PitObservation


def normalize_pit_reports(
    rows, *, entries_by_car, clock_origin, session_key, publication_margin_s=15
):
    if clock_origin.tzinfo is None:
        raise ValueError("Clock origin must be timezone-aware")
    output = []
    for row in rows:
        if row.get("session_key") != session_key:
            raise ValueError("OpenF1 response contains a different session")
        car = str(row.get("driver_number"))
        if car not in entries_by_car:
            raise ValueError("OpenF1 driver does not belong to this session")
        stamp = datetime.fromisoformat(str(row["date"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Source pit timestamps must include timezone")
        event = round((stamp - clock_origin).total_seconds() * 1000)
        lane = row.get("lane_duration", row.get("pit_duration"))
        stationary = row.get("stop_duration")
        if lane is None and stationary is None:
            continue
        # The source date's exact point within the visit is unspecified. Never assume instant publication.
        delay = max(float(lane or 0), float(stationary or 0)) + publication_margin_s
        known = event + math.ceil(delay * 1000)
        output.append(
            PitObservation(
                entry_id=entries_by_car[car],
                lap_number=int(row["lap_number"]),
                event_time_ms=event,
                known_at_ms=known,
                lane_duration_s=lane,
                stationary_duration_s=stationary,
                source_uri=f"https://api.openf1.org/v1/pit?session_key={session_key}",
            )
        )
    return output
