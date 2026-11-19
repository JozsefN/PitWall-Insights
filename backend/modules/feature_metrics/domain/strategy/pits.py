import numpy as np
from .common import clean_laps, mad, phase_at, clear_interval, band


def latest_pit_transitions(entry, cutoff):
    def last(key):
        return max(
            (
                lap[key]
                for lap in entry.laps
                if lap.get(key) is not None and lap[key] <= cutoff
            ),
            default=-1,
        )

    return last("pit_in_time_ms"), last("pit_out_time_ms")


def visits(entry, cutoff):
    ins = sorted(
        {
            row["pit_in_time_ms"]: row
            for row in entry.laps
            if row.get("pit_in_time_ms") is not None and row["pit_in_time_ms"] <= cutoff
        }.items()
    )
    outs = sorted(
        {
            row["pit_out_time_ms"]: row
            for row in entry.laps
            if row.get("pit_out_time_ms") is not None
            and row["pit_out_time_ms"] <= cutoff
        }.items()
    )
    used = -1
    output = []
    for start, inlap in ins:
        if start <= used:
            continue
        following = next(
            ((end, row) for end, row in outs if end > start and end > used), None
        )
        if following:
            end, outlap = following
            used = end
            output.append(
                dict(
                    entry_id=entry.id,
                    start=start,
                    end=end,
                    lane_s=(end - start) / 1000,
                    inlap=inlap,
                    outlap=outlap,
                )
            )
    return output


def net_loss_from_pair(data, clean, inlap, outlap, cutoff, baseline_lap_distance=1):
    if outlap["lap_number"] != inlap["lap_number"] + 1:
        return None
    if any(
        not row.get("lap_time_ms") or row.get("is_generated") or row.get("is_deleted")
        for row in (inlap, outlap)
    ):
        return None
    start, end = inlap.get("lap_start_time_ms"), outlap.get("lap_end_time_ms")
    if (
        start is None
        or end is None
        or end > cutoff
        or not clear_interval(data, start, end)
    ):
        return None
    before = next(
        (
            row
            for row in reversed(clean)
            if 0 < inlap["lap_number"] - row["lap_number"] <= baseline_lap_distance
        ),
        None,
    )
    after = next(
        (
            row
            for row in clean
            if 0 < row["lap_number"] - outlap["lap_number"] <= baseline_lap_distance
        ),
        None,
    )
    if before is None or after is None:
        return None
    loss = (
        inlap["lap_time_ms"]
        + outlap["lap_time_ms"]
        - before["lap_time_ms"]
        - after["lap_time_ms"]
    ) / 1000
    return (
        {
            "net_loss_s": loss,
            "known_at_ms": after["lap_end_time_ms"],
            "stop_lap_end_ms": inlap["lap_end_time_ms"],
            "baseline_laps": [before["lap_number"], after["lap_number"]],
        }
        if 0 < loss < 100
        else None
    )


def empirical_pit_losses(data, cutoff, all_visits=None):
    if all_visits is None:
        all_visits = [
            {**visit, "phase": phase_at(data, visit["start"])}
            for entry in data.entries
            for visit in visits(entry, cutoff)
        ]
    losses = []
    for entry in data.entries:
        clean = clean_laps(entry, cutoff)
        for visit in all_visits:
            if visit["entry_id"] != entry.id or visit["phase"] != "1":
                continue
            loss = net_loss_from_pair(
                data, clean, visit["inlap"], visit["outlap"], cutoff
            )
            if loss:
                losses.append(
                    {**loss, "entry_id": entry.id, "lane_duration_s": visit["lane_s"]}
                )
    return losses


def pit_features(data, request, context, result):
    focus = next(entry for entry in data.entries if entry.id == request.focus_entry_id)
    all_visits = [
        visit for entry in data.entries for visit in visits(entry, request.as_of_ms)
    ]
    for visit in all_visits:
        visit["phase"] = phase_at(data, visit["start"])
        if any(
            str(row["status"]) != visit["phase"]
            for row in data.track_status
            if visit["start"] < row["session_time_ms"] <= visit["end"]
        ):
            visit["phase"] = "mixed"
    own = [visit for visit in all_visits if visit["entry_id"] == focus.id]
    last = own[-1] if own else None
    baseline = [
        visit["lane_s"]
        for visit in all_visits
        if last
        and visit["phase"] == last["phase"]
        and visit is not last
        and visit["phase"] in ("1", "4", "6")
    ]
    centre = float(np.median(baseline)) if len(baseline) >= 3 else None
    result.put(
        "pit_latest_lane_duration_s",
        last["lane_s"] if last else None,
        focus.id,
        n=len(own),
        status="observed",
    )
    result.put(
        "pit_field_lane_baseline_s",
        centre,
        focus.id,
        n=len(baseline),
        status="estimated",
    )
    result.put(
        "pit_latest_lane_excess_s",
        last["lane_s"] - centre if centre is not None else None,
        focus.id,
        n=len(baseline),
        status="estimated",
    )
    reports = (
        [row for row in context.pit_observations if row.known_at_ms <= request.as_of_ms]
        if context
        else []
    )
    own_reports = sorted(
        (
            row
            for row in reports
            if row.entry_id == focus.id and row.stationary_duration_s is not None
        ),
        key=lambda row: row.event_time_ms,
    )
    latest = own_reports[-1] if own_reports else None
    others = [
        row.stationary_duration_s
        for row in reports
        if latest
        and row is not latest
        and row.stationary_duration_s is not None
        and phase_at(data, row.event_time_ms) == phase_at(data, latest.event_time_ms)
    ]
    result.put(
        "pit_latest_stationary_duration_s",
        latest.stationary_duration_s if latest else None,
        focus.id,
        n=len(own_reports),
        status="observed",
    )
    result.put(
        "pit_stationary_excess_s",
        (
            latest.stationary_duration_s - float(np.median(others))
            if latest and len(others) >= 3
            else None
        ),
        focus.id,
        n=len(others),
        status="estimated",
    )
    losses = [
        row["net_loss_s"]
        for row in empirical_pit_losses(data, request.as_of_ms, all_visits)
    ]
    net = float(np.median(losses)) if len(losses) >= 3 else None
    dispersion = mad(losses) if len(losses) >= 3 else None
    result.put(
        "pit_net_loss_estimate_s",
        net,
        focus.id,
        n=len(losses),
        status="estimated",
        warnings=[
            "Neighbour-lap estimator includes tyre/warmup/traffic effects, not a directly measured net pit loss."
        ],
    )
    result.put(
        "pit_net_loss_scatter_s",
        dispersion,
        focus.id,
        n=len(losses),
        status="estimated",
    )
    model = context.pit_loss if context else None
    value = model.green_s if model else net
    error = model.uncertainty_s if model else max(2, dispersion or 0)
    result.put(
        "pit_green_loss_input_s",
        value,
        focus.id,
        n=len(losses),
        status=(
            "assumed" if model and model.provenance == "user_scenario" else "estimated"
        ),
        bounds=band(value, error) if value is not None else None,
        support={"source": model.source_uri if model else "paired_completed_laps"},
    )
    result.put(
        "pit_sc_discount_s",
        model.green_s - model.sc_s if model and model.sc_s is not None else None,
        focus.id,
        status=(
            "assumed" if model and model.provenance == "user_scenario" else "estimated"
        ),
    )
    result.put(
        "pit_vsc_discount_s",
        model.green_s - model.vsc_s if model and model.vsc_s is not None else None,
        focus.id,
        status=(
            "assumed" if model and model.provenance == "user_scenario" else "estimated"
        ),
    )
    track = context.track if context else None
    latest_position = focus.positions[-1] if focus.positions else None
    eta = None
    distance = None
    age_increment = 0.0
    eta_method = None
    pace = result.get("strategy_recent_pace_s", focus.id)
    if (
        track
        and track.pit_entry_progress_pct is not None
        and data.reference is not None
        and latest_position
        and request.as_of_ms - latest_position["session_time_ms"] <= 2000
    ):
        xy = (
            np.array(
                [[latest_position.get("x"), latest_position.get("y")]], dtype=float
            )
            * 0.1
        )
        if np.all(np.isfinite(xy)) and np.any(xy):
            deviation, progress = data.reference.project(xy)
            if deviation[0] <= 15:
                fraction = (track.pit_entry_progress_pct - progress[0]) % 100 / 100
                distance = fraction * data.reference.length
                age_increment = track.pit_entry_progress_pct / 100 + (
                    1 if progress[0] > track.pit_entry_progress_pct else 0
                )
                historical = data.reference.forward_time_s(
                    float(progress[0]), track.pit_entry_progress_pct
                )
                if historical is not None and pace is not None:
                    eta = historical * pace / (data.reference.lap_duration_ms / 1000)
                    eta_method = "historical_local_transit_scaled_by_median_pace"
                elif pace is not None:
                    eta = pace * fraction
                    eta_method = "lap_average_speed_fallback"
    result.put("pit_next_entry_distance_m", distance, focus.id, status="estimated")
    result.put(
        "pit_next_entry_eta_s",
        eta,
        focus.id,
        status="estimated",
        bounds=band(eta, max(1, 0.2 * eta)) if eta is not None else None,
        support={"method": eta_method},
        warnings=[
            "Reference/average pace cannot foresee local traffic, braking or changed flags."
        ],
    )
    return dict(
        visits=all_visits,
        reports=reports,
        loss=value,
        error=error,
        model=model,
        decision_eta_s=eta,
        decision_age_increment_laps=age_increment,
    )


def pit_windows(data, request, context, result, pairs, pit):
    focus = request.focus_entry_id
    rejoin = []
    for rival, state in pairs.items():
        gap = state["gap"]
        loss = pit["loss"]
        eta = pit.get("decision_eta_s")
        if gap is not None and eta is not None:
            gap -= (
                state.get("closing_rate", 0) * eta
                if state.get("closing_rate") is not None
                else 0
            )
        after = gap + loss if gap is not None and loss is not None else None
        error = state["error"] + pit["error"]
        result.put(
            "pit_rejoin_gap_vs_rival_s",
            after,
            focus,
            rival,
            status="estimated",
            bounds=band(after, error) if after is not None else None,
            support={
                "decision_eta_s": eta,
                "gap_constant_until_entry_assumption": eta is None,
            },
            warnings=[
                "Conditional rejoin model, not a measured future classification."
            ],
        )
        result.put(
            "pit_free_stop_margin_s",
            -after if after is not None else None,
            focus,
            rival,
            status="estimated",
        )
        if after is not None:
            rejoin.append(after)
        rival_visits = [
            visit
            for visit in pit["visits"]
            if visit["entry_id"] == rival
            and state["anchor_time_ms"] is not None
            and visit["end"] <= state["anchor_time_ms"]
        ]
        latest = rival_visits[-1] if rival_visits else None
        peers = [
            visit["lane_s"]
            for visit in pit["visits"]
            if latest
            and visit is not latest
            and visit["phase"] == latest["phase"]
            and latest["phase"] in ("1", "4", "6")
        ]
        excess = (
            latest["lane_s"] - float(np.median(peers))
            if latest and len(peers) >= 3
            else None
        )
        # Prefer actual service reports only when tied to that already incorporated stop.
        services = [
            row
            for row in pit["reports"]
            if latest
            and row.entry_id == rival
            and row.lap_number == latest["inlap"]["lap_number"]
            and row.stationary_duration_s is not None
            and row.known_at_ms <= state["anchor_time_ms"]
        ]
        excess_error = max(1, mad(peers) or 0)
        if services:
            report = services[-1]
            normal = [
                row.stationary_duration_s
                for row in pit["reports"]
                if row is not report
                and row.stationary_duration_s is not None
                and phase_at(data, row.event_time_ms) == latest["phase"]
            ]
            if len(normal) >= 3:
                excess = report.stationary_duration_s - float(np.median(normal))
                excess_error = max(0.3, mad(normal) or 0)
        counter = gap + excess if gap is not None and excess is not None else None
        opportunity = (
            (after + error < 0 and counter + loss - error - excess_error >= 0)
            if after is not None and counter is not None and excess > 0
            else None
        )
        result.put(
            "pit_rival_normal_stop_counterfactual_gap_s",
            counter,
            focus,
            rival,
            status="estimated",
            support={
                "excess_s": excess,
                "stop_end_ms": latest["end"] if latest else None,
            },
        )
        result.put(
            "pit_rival_delay_creates_window",
            opportunity,
            focus,
            rival,
            status="estimated",
            warnings=[
                "Conditional on comparable delay baseline and own pit cost; does not itself require or recommend a stop."
            ],
        )
    all_ids = {entry.id for entry in data.entries} - {focus}
    rank = (
        1 + sum(gap > 0 for gap in rejoin)
        if set(pairs) == all_ids and len(rejoin) == len(all_ids)
        else None
    )
    result.put(
        "strategy_rejoin_rank_estimate", rank, focus, status="estimated", n=len(rejoin)
    )
