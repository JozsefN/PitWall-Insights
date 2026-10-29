"""Pure calculations. No database, network or replay worker dependency."""

from datetime import datetime, timezone
from .catalog import selected_definitions
from .common import Results
from .models import AnalysisResponse
from .laps import calculate_laps, calculate_stints
from .telemetry import calculate_speed, calculate_controls, calculate_powertrain
from .position import calculate_position, calculate_quality
from .incidents import calculate_incidents
from .racing import calculate_racing
from .conditions import calculate_conditions

CALCULATORS = dict(
    laps=calculate_laps,
    stints=calculate_stints,
    speed=calculate_speed,
    controls=calculate_controls,
    powertrain=calculate_powertrain,
    position=calculate_position,
    quality=calculate_quality,
    incidents=calculate_incidents,
    racing=calculate_racing,
    conditions=calculate_conditions,
)


def analyze(data, request, fingerprint="synthetic"):
    selected = selected_definitions(request)
    result = Results(request)
    for group in dict.fromkeys(definition.group for definition in selected):
        CALCULATORS[group](data, request, result)
    metrics = []
    for definition in selected:
        entries = (
            [None]
            if definition.scope == "session"
            else [entry.id for entry in data.entries]
        )
        for entry in entries:
            # A registered metric without an implementation is a programming error.
            metrics.append(result.metrics[(definition.metric_id, entry)])
    events = sorted(
        result.events,
        key=lambda event: (event.start_time_ms, event.entry_id or "", event.kind),
    )
    warnings = [
        "Sampling affects brief events and peak values. Confidence scores are support heuristics, not calibrated probabilities.",
        "Speed drops, source OffTrack flags and distance from a racing line do not establish a crash or a track-limits breach.",
    ]
    return AnalysisResponse(
        session_id=data.session_id,
        computed_at=datetime.now(timezone.utc),
        start_time_ms=data.start_ms,
        end_time_ms=data.end_ms,
        sample_interval_ms=request.sample_interval_ms,
        data_fingerprint=fingerprint,
        coverage=data.coverage,
        metrics=metrics,
        events=events,
        total_event_count=result.total_events,
        events_truncated=request.include_events and result.total_events > len(events),
        warnings=warnings,
    )
