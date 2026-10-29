"""Retrospective, censored non-pit stop cohorts with independent incident identities."""

from datetime import timedelta
import numpy as np
from modules.feature_metrics.domain.analysis.common import numeric, weights, episodes
from modules.feature_metrics.domain.strategy.rivals import pit_mask
from .common import phase_at
from .models import IncidentHistory


def collect_incident_history(data, *, circuit_key, clock_origin, horizon_s=120):
    stops = []
    for entry in data.entries:
        times = numeric(entry.car, "session_time_ms")
        speed = numeric(entry.car, "speed_kph")
        duration = weights(times, data.start_ms, data.end_ms, 2000)
        for start, end, seconds in episodes(
            np.isfinite(speed) & (speed >= 0) & (speed <= 5) & ~pit_mask(entry, times),
            times,
            duration,
        ):
            if seconds >= 4:
                stops.append(
                    dict(
                        entry_id=entry.id,
                        start=int(times[start]),
                        end=int(times[end - 1]),
                        duration_s=seconds,
                    )
                )
    output = []
    for stop in stops:
        # A single-car model must not count two cars from one multi-car incident as independent examples.
        if any(
            other is not stop
            and other["entry_id"] != stop["entry_id"]
            and abs(other["start"] - stop["start"]) < 10000
            for other in stops
        ):
            continue
        incident_id = f"{data.session_id}:{stop['entry_id']}:{stop['start']}"
        for elapsed, label in ((5, "4_10"), (15, "10_30"), (35, "30_plus")):
            anchor = stop["start"] + elapsed * 1000
            end = anchor + horizon_s * 1000
            if (
                anchor > stop["end"]
                or end > data.end_ms
                or phase_at(data, anchor) not in ("1", "2")
            ):
                continue
            future = [
                str(row["status"])
                for row in data.track_status
                if anchor < row["session_time_ms"] <= end
            ]
            if any(code not in ("1", "2", "4", "5", "6", "7") for code in future):
                continue
            outcome = (
                "red"
                if "5" in future
                else (
                    "sc"
                    if "4" in future
                    else "vsc" if set(future) & {"6", "7"} else "none"
                )
            )
            output.append(
                IncidentHistory(
                    observation_id=incident_id + ":" + label,
                    incident_id=incident_id,
                    circuit_key=circuit_key,
                    observed_at_utc=clock_origin + timedelta(milliseconds=anchor),
                    stopped=True,
                    surface="unknown",
                    recovery_access="unknown",
                    elapsed_stop_bin=label,
                    horizon_s=horizon_s,
                    outcome=outcome,
                    sc_occurred="4" in future,
                    vsc_occurred=bool(set(future) & {"6", "7"}),
                    red_occurred="5" in future,
                    source_uri=f"pitwall:session:{data.session_id}:car-and-track-status",
                )
            )
    return output
