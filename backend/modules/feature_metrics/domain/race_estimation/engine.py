from statistics import median
from .models import RaceEstimateResponse, RaceContext
from .catalog import MODEL_NOTES
from .common import conditions_at, number
from .traffic import TrafficContext
from .driver import evaluate_driver
from .events import reported_events
from .racing import battle_snapshot
from modules.feature_metrics.domain.snapshot import causal_snapshot
from modules.feature_metrics.domain.analysis.common import json_safe


def visible_context(context, cutoff, delay):
    pits = []
    for row in context.pits:
        duration = max(
            number(row.get("lane_duration", row.get("pit_duration"))) or 0,
            number(row.get("stop_duration")) or 0,
        )
        known = row.get(
            "known_at_ms", row["session_time_ms"] + int(duration * 1000) + delay
        )
        if known <= cutoff:
            pits.append({**row, "known_at_ms": known})
    return RaceContext(
        driver_ids=context.driver_ids,
        intervals=[
            row for row in context.intervals if row["session_time_ms"] + delay <= cutoff
        ],
        positions=[
            row for row in context.positions if row["session_time_ms"] + delay <= cutoff
        ],
        pits=pits,
        overtakes=[
            row for row in context.overtakes if row["session_time_ms"] + delay <= cutoff
        ],
    )


def estimate_race(data, context, request, fingerprint="synthetic"):
    data = causal_snapshot(data, request.as_of_ms, request.lookback_ms)
    if request.entry_ids is not None and set(request.entry_ids) - {
        entry.id for entry in data.entries
    }:
        raise ValueError("Every selected entry must belong to this session")
    context = visible_context(
        context, request.as_of_ms, request.assumptions.source_report_delay_ms
    )
    traffic = TrafficContext(context, request)
    clocks = sorted(
        {
            request.as_of_ms,
            *[row["session_time_ms"] for entry in data.entries for row in entry.car],
        }
    )
    traffic_samples = {stamp: traffic.snapshot(stamp) for stamp in clocks}
    conditions = conditions_at(data, request)
    drivers = []
    events = []
    for entry in data.entries:
        result, candidates = evaluate_driver(
            entry, data, context, request, traffic_samples, traffic, conditions
        )
        drivers.append(result)
        events.extend(candidates)
    end = traffic_samples[request.as_of_ms]
    by_id = {driver.entry_id: driver for driver in drivers}
    pairs = []
    for driver in drivers:
        detail = end.get(driver.car_number, {})
        front_id = detail.get("ahead_id")
        if not front_id:
            continue
        gap = driver.metrics["ahead_gap_s"].value
        closing = driver.metrics["gap_closing_rate"].value
        attack = driver.metrics["attack_opportunity_index"].value
        pairs.append(
            {
                "follower_id": driver.entry_id,
                "ahead_id": front_id,
                "gap_s": gap,
                "closing_rate": closing,
                "projected_gap_s": driver.metrics["projected_gap_s"].value,
                "catch_time_s": driver.metrics["catch_time_s"].value,
                "attack_index": attack,
                "support": driver.metrics["ahead_gap_s"].support,
            }
        )
        if front_id in by_id:
            front = by_id[front_id]
            pressure = front.metrics["defence_pressure_index"]
            if isinstance(attack, (int, float)) and (
                pressure.value is None or attack > pressure.value
            ):
                front.metrics["defence_pressure_index"] = driver.metrics[
                    "attack_opportunity_index"
                ].model_copy()
    for driver in drivers:
        neighbours = sum(
            p["gap_s"] is not None
            and p["gap_s"] <= request.assumptions.traffic_gap_s
            and driver.entry_id in (p["follower_id"], p["ahead_id"])
            for p in pairs
        )
        base = driver.metrics["ahead_gap_s"].model_copy(
            update={
                "unit": "count",
                "method": "derived",
                "status": "available",
                "value": float(neighbours),
                "support": 0.7,
                "reason": None,
            }
        )
        if neighbours or driver.car_number in end:
            driver.metrics["nearby_car_count"] = base.model_copy(
                update={
                    "reason": "Count of supported adjacent-car reports within the configured gap; missing reports can hide other cars."
                }
            )
        # No follower report is missing evidence, not proof of zero pressure.
        pit_values(driver, context, request, conditions, pairs)
    battles, passes = battle_snapshot(data, context, request)
    rows_by_pair = {(row["follower_id"], row["ahead_id"]): row for row in battles}
    for pair in pairs:
        row = rows_by_pair.get((pair["follower_id"], pair["ahead_id"]))
        if row:
            pair.update(row)
    events.extend(passes)
    events.extend(reported_events(data, context, request))
    selected = set(request.entry_ids) if request.entry_ids is not None else None
    drivers = [
        driver for driver in drivers if selected is None or driver.entry_id in selected
    ]
    # Global flags and competitors' reports remain visible to contextual notification panels.
    deduplicated = {
        item.id: item
        for item in events
        if data.start_ms <= item.time_ms <= request.as_of_ms
    }
    events = sorted(
        deduplicated.values(), key=lambda item: (item.time_ms, item.id), reverse=True
    )
    count = len(events)
    events = events[: request.max_events]
    warnings = list(MODEL_NOTES)
    if conditions.get("rain_reported"):
        warnings.append(
            "Rain is reported. Dry grip, wake and pit scenarios are not wet-track calibration."
        )
    if not any(driver.metrics["observed_window_s"].value for driver in drivers):
        warnings.append(
            "Car telemetry is missing for the selection. Only supported timing and race-control context is available."
        )
    return RaceEstimateResponse(
        session_id=data.session_id,
        as_of_ms=request.as_of_ms,
        start_ms=data.start_ms,
        fingerprint=fingerprint,
        assumptions=request.assumptions.model_dump(),
        drivers=drivers,
        pairs=pairs,
        events=events,
        event_count=count,
        events_truncated=count > len(events),
        conditions=json_safe(conditions),
        warnings=warnings,
    )


def pit_values(driver, context, request, conditions, pairs):
    from .common import Values

    result = Values()
    result.metrics = driver.metrics
    lane = [
        number(row.get("lane_duration", row.get("pit_duration")))
        for row in context.pits
    ]
    lane = [value for value in lane if value is not None and value > 0]
    result.put("pit_lane_duration_median_s", median(lane) if lane else None, 0.8)
    own = sorted(
        (row for row in context.pits if row["driver_number"] == driver.car_number),
        key=lambda row: row.get("known_at_ms", row["session_time_ms"]),
    )
    if own:
        latest = own[-1]
        stationary = number(latest.get("stop_duration")) is not None

        def duration(row):
            return (
                number(row.get("stop_duration"))
                if stationary
                else number(row.get("lane_duration", row.get("pit_duration")))
            )

        reference = [
            duration(row)
            for row in context.pits
            if row.get("known_at_ms", row["session_time_ms"])
            < latest.get("known_at_ms", latest["session_time_ms"])
        ]
        reference = [value for value in reference if value is not None and value > 0]
        result.put(
            "latest_stop_delta_s",
            duration(latest) - median(reference) if reference else None,
            0.75,
            reason="Compared with earlier same-type duration reports; this is not proof of crew error.",
        )
    phase = conditions["track_status"]
    factor = {"1": 1.0, "2": 1.0, "4": 0.55, "6": 0.7, "7": 0.7}.get(phase)
    loss = (
        request.assumptions.pit_loss_scenario_s * factor if factor is not None else None
    )
    result.put(
        "pit_loss_scenario_s",
        loss,
        0.25,
        lower=loss * 0.7 if loss is not None else None,
        upper=loss * 1.3 if loss is not None else None,
        reason="Configured net pit-loss assumption. SC/VSC factors are scenarios, not circuit calibration.",
    )
    rear = next(
        (
            pair
            for pair in pairs
            if pair["ahead_id"] == driver.entry_id and pair["gap_s"] is not None
        ),
        None,
    )
    margin = rear["gap_s"] - loss if rear and loss is not None else None
    result.put(
        "pit_exit_margin_scenario_s",
        margin,
        0.25,
        lower=rear["gap_s"] - loss * 1.3 if margin is not None else None,
        upper=rear["gap_s"] - loss * 0.7 if margin is not None else None,
        reason="Next-car time-margin scenario only; pit exit geometry, the rest of the field and rival strategy are not resolved.",
    )
    traffic = driver.metrics["traffic_correlated_loss_s"].value
    gain = request.assumptions.fresh_tyre_gain_scenario_s - (
        max(0, traffic) if isinstance(traffic, (int, float)) else 0
    )
    result.put(
        "one_lap_undercut_scenario_s",
        gain,
        0.2,
        lower=gain - 1.5,
        upper=gain + 1.5,
        reason="Assumed fresh-tyre gain; unavailable traffic loss is left out of the scenario. This is not an optimal pit recommendation.",
    )
