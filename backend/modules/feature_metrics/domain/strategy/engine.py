from dataclasses import replace
from datetime import datetime, timezone
from .models import StrategyResponse
from .common import Values
from .pace import pace_features
from .rivals import rival_features
from .pits import pit_features, pit_windows
from .spatial import motion, wind_physics
from .risk import incident_risk
from modules.feature_metrics.domain.analysis.common import json_safe


def causal_snapshot(data, cutoff, lookback_ms=None):
    window_start = (
        max(data.start_ms, cutoff - lookback_ms)
        if lookback_ms is not None
        else data.start_ms
    )
    window_start = min(window_start, cutoff)
    entries = []
    for entry in data.entries:
        laps = []
        for row in entry.laps:
            if row.get("is_generated"):
                continue
            lap_start = row.get("lap_start_time_ms")
            if lap_start is None or lap_start > cutoff:
                continue
            if (
                row.get("lap_end_time_ms") is not None
                and row["lap_end_time_ms"] <= cutoff
            ):
                visible = dict(row)
            else:
                # Current-lap results, tyre choice, flags and end position are future metadata.
                visible = {
                    key: row.get(key)
                    for key in ("id", "lap_number", "lap_start_time_ms")
                }
                for sector in range(1, 4):
                    stamp = row.get(f"sector_{sector}_session_time_ms")
                    if stamp is not None and stamp <= cutoff:
                        visible[f"sector_{sector}_session_time_ms"] = stamp
                        visible[f"sector_{sector}_time_ms"] = row.get(
                            f"sector_{sector}_time_ms"
                        )
            for key in ("pit_in_time_ms", "pit_out_time_ms"):
                value = row.get(key)
                visible[key] = value if value is not None and value <= cutoff else None
            laps.append(visible)
        entries.append(
            replace(
                entry,
                laps=laps,
                stints=[],
                car=[
                    row
                    for row in entry.car
                    if window_start <= row["session_time_ms"] <= cutoff
                ],
                positions=[
                    row
                    for row in entry.positions
                    if window_start <= row["session_time_ms"] <= cutoff
                ],
            )
        )
    reference = data.reference
    if (
        reference is not None
        and reference.lap_id is not None
        and not any(
            row.get("id") == reference.lap_id and row.get("lap_end_time_ms") is not None
            for entry in entries
            for row in entry.laps
        )
    ):
        reference = None
    return replace(
        data,
        entries=entries,
        start_ms=window_start,
        end_ms=cutoff,
        reference=reference,
        weather=[row for row in data.weather if row["session_time_ms"] <= cutoff],
        track_status=[
            row for row in data.track_status if row["session_time_ms"] <= cutoff
        ],
        race_control=[
            row for row in data.race_control if row["session_time_ms"] <= cutoff
        ],
    )


def strategy_features(
    data, request, context=None, *, context_id=None, fingerprint="synthetic"
):
    """Feature layer only; the decision engine supplies planning after these dependencies."""
    if context is not None and context.known_at_ms > request.as_of_ms:
        raise ValueError("Context was not known at decision time")
    if context is not None:
        year = data.coverage.get("season_year")
        frame = data.coverage.get("coordinate_frame")
        if context.track and (
            (frame and frame != context.track.coordinate_frame)
            or (
                year
                and not context.track.valid_season_from
                <= year
                <= context.track.valid_season_to
            )
        ):
            raise ValueError(
                "Track calibration does not match this session frame/season"
            )
        if context.rules and year and context.rules.season_year != year:
            raise ValueError("Rule profile does not match this session season")
    data = causal_snapshot(data, request.as_of_ms, request.telemetry_lookback_ms)
    ids = {entry.id for entry in data.entries}
    if request.focus_entry_id not in ids or set(request.rival_entry_ids or []) - ids:
        raise ValueError("Every selected entry must belong to the session")
    result = Values(request.as_of_ms)
    models = {"pace": pace_features(data, request, result)}
    series, pairs = rival_features(data, request, result)
    pit = pit_features(data, request, context, result)
    pit_windows(data, request, context, result, pairs, pit)
    states = {}
    for entry in data.entries:
        states[entry.id] = dict(
            motion(entry, data, request, context, result), entry_id=entry.id
        )
    focus = next(entry for entry in data.entries if entry.id == request.focus_entry_id)
    wind_physics(focus, data, request, context, states[focus.id], result)
    active = [
        state
        for state in states.values()
        if (state["stopped"] or state["collision"])
        and not state["in_pit"]
        and state["state"] != "stale"
    ]
    if len(active) <= 1:
        models["safety_car"] = incident_risk(
            data, request, context, active[0] if active else states[focus.id], result
        )
    else:
        models["safety_car"] = {
            "probability_available": False,
            "reason": "Multiple active cars require a joint incident cohort; independent incident probabilities must not be multiplied.",
        }
    events = [
        dict(
            kind="incident_state",
            entry_id=entry_id,
            state=state["state"],
            surface=state["surface"],
            candidate_collision=state["collision"],
            candidate_only=True,
            as_of_ms=request.as_of_ms,
        )
        for entry_id, state in states.items()
        if state["stopped"] or state["collision"]
    ]
    readiness = {
        "active_incident_entries": [state["entry_id"] for state in active],
        "coverage": data.coverage,
        "context_supplied": context is not None,
        "coordinate_frame": data.coverage.get("coordinate_frame"),
        "track_boundaries_supplied": bool(
            context
            and context.track
            and any(zone.kind == "racing_surface" for zone in context.track.zones)
        ),
        "north_alignment_supplied": bool(
            context and context.track and context.track.north_angle_xy_deg is not None
        ),
        "physics_is_lap_time_correction": False,
        "arrival_time_reconstruction": False,
    }
    return data, result, models, series, pit, events, readiness


def response(
    data,
    request,
    context_id,
    fingerprint,
    result,
    models,
    series,
    events,
    readiness,
    plans,
    winner,
    status,
):
    rivals = [
        entry.id
        for entry in data.entries
        if entry.id != request.focus_entry_id
        and (request.rival_entry_ids is None or entry.id in request.rival_entry_ids)
    ]
    result.fill(request.focus_entry_id, rivals)
    return StrategyResponse(
        session_id=data.session_id,
        as_of_ms=request.as_of_ms,
        context_id=context_id,
        data_fingerprint=fingerprint,
        computed_at=datetime.now(timezone.utc),
        values=list(result.values.values()),
        pair_series=json_safe(series),
        events=json_safe(events),
        models=json_safe(models),
        plans=plans,
        best_modeled_plan=winner,
        recommendation_status=status,
        readiness=json_safe(readiness),
        warnings=[
            "Best plan means lowest modeled time among the configured candidates, not guaranteed best real-world strategy.",
            "Unavailable geometry, tyre inventory, aero coefficients and calibration are not guessed.",
            "Historical lap accuracy/deletion metadata may be revised after the race: event-time replay is not a reconstruction of when each fact originally arrived.",
            "No model in this endpoint uses AI. Statistical intervals and conditional scenario bounds are identified separately.",
        ],
    )
