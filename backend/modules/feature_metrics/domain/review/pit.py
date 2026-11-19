"""Pit benchmarks and explicit counterfactuals, independent of HTTP/persistence."""

from statistics import median

from ..race_estimation.common import number, phase_at
from ..strategy.common import mad, clean_laps
from ..strategy.pits import empirical_pit_losses, net_loss_from_pair
from .pace import rain_state


def benchmark(samples, value, minimum=3):
    rows = [
        row for row in samples if number(row.get(value)) is not None and row[value] > 0
    ]
    values = [row[value] for row in rows]
    return {
        "sample_count": len(values),
        "median_s": median(values) if len(values) >= minimum else None,
        "robust_scatter_s": mad(values) if len(values) >= minimum else None,
        "session_ids": sorted({row["session_id"] for row in rows}),
    }


def comparable_stop_excess(report, comparable):
    key = (
        "stationary_duration_s"
        if report.get("stationary_duration_s") is not None
        else "lane_duration_s"
    )
    duration = report.get(key)
    reference = benchmark([row for row in comparable if row is not report], key)
    if duration is None or reference["median_s"] is None:
        return None
    return {
        "basis": "stationary" if key == "stationary_duration_s" else "lane",
        "excess_s": duration - reference["median_s"],
        "scatter_s": reference["robust_scatter_s"],
        "samples": reference["sample_count"],
    }


def pit_review(data, cutoff, historical, reports, field, pace, repair_extra, incidents):
    race_losses = []
    comparable_reports = []
    current_rain = rain_state(data, cutoff)
    for session, limit in [
        (data, cutoff),
        *((past, past.end_ms) for past in historical),
    ]:
        source_reports = [
            row
            for row in reports
            if row["session_id"] == session.session_id and row["known_at_ms"] <= limit
        ]
        native = native_net_losses(session, limit, source_reports)
        fallback = empirical_pit_losses(session, limit) if not native else []
        race_losses.extend(
            {**row, "session_id": session.session_id}
            for row in [*native, *fallback]
            if current_rain is None
            or rain_state(session, row["stop_lap_end_ms"]) is current_rain
        )
        comparable_reports.extend(
            row
            for row in source_reports
            if phase_at(session.track_status, row["event_time_ms"]) == "1"
            and (
                current_rain is None
                or rain_state(session, row["event_time_ms"]) is current_rain
            )
        )
    net = benchmark(race_losses, "net_loss_s")
    lane = benchmark(reports, "lane_duration_s")
    stationary = benchmark(reports, "stationary_duration_s")
    current_phase = phase_at(data.track_status, cutoff)
    net_loss = net["median_s"] if current_phase == "1" else None
    by_pace = {row["entry_id"]: row for row in pace if row["samples"] >= 3}
    offsets = {
        row["entry_id"]: row["current_gap_to_leader_s"]
        for row in field
        if row.get("projected_elapsed_s") is not None
    }
    damage_ids = {
        entry
        for item in incidents
        if item["kind"] == "damage_report"
        for entry in item["entry_ids"]
    }
    scenarios = []
    rival_windows = []
    for entry_id, gap in offsets.items():
        if net_loss is None:
            break
        pit_offset = gap + net_loss
        position = 1 + sum(
            value < pit_offset for key, value in offsets.items() if key != entry_id
        )
        repair_loss = (
            net_loss + repair_extra
            if entry_id in damage_ids and repair_extra is not None
            else None
        )
        scenarios.append(
            {
                "entry_id": entry_id,
                "added_net_loss_s": net_loss,
                "projected_gap_to_current_leader_s": pit_offset,
                "exit_order_among_timed_entries": position,
                "timed_entries": len(offsets),
                "extra_repair_s_assumption": (
                    repair_extra if repair_loss is not None else None
                ),
                "total_repair_stop_loss_s": repair_loss,
            }
        )
        own_pace = by_pace[entry_id]["median_pace_s"]
        latest = {}
        for report in comparable_reports:
            if (
                report["session_id"] == data.session_id
                and report["entry_id"] != entry_id
                and report["known_at_ms"] <= cutoff
            ):
                rival = report["entry_id"]
                if (
                    rival not in latest
                    or report["known_at_ms"] > latest[rival]["known_at_ms"]
                ):
                    latest[rival] = report
        for rival, report in latest.items():
            if (
                rival not in offsets
                or rival not in by_pace
                or cutoff - report["known_at_ms"] > 150000
            ):
                continue
            if abs(by_pace[rival]["median_pace_s"] - own_pace) > 0.75:
                continue
            measured = comparable_stop_excess(report, comparable_reports)
            if measured is None or measured["excess_s"] < 1:
                continue
            excess = measured["excess_s"]
            margin_now = offsets[rival] - pit_offset
            margin_normal = margin_now - excess
            rival_windows.append(
                {
                    "entry_id": entry_id,
                    "rival_entry_id": rival,
                    "rival_stop_excess_s": excess,
                    "exit_margin_s": margin_now,
                    "normal_rival_stop_margin_s": margin_normal,
                    "position_flip_scenario": margin_now > 0 >= margin_normal,
                }
            )
    return {
        "net_green_pit_loss": net,
        "pit_lane_duration": lane,
        "stationary_service_duration": stationary,
        "exit_scenarios": scenarios,
        "rival_windows": rival_windows,
        "rain_cohort": (
            "rain_flagged"
            if current_rain is True
            else "no_rain_flag" if current_rain is False else "unspecified"
        ),
        "method": "Net loss compares a completed in/out pair with the nearest clean laps within three laps on each side. Exit order holds other drivers’ timing offsets fixed. Practice and prior race sessions must be stored at this circuit.",
    }


def native_net_losses(data, cutoff, reports):
    entries = {entry.id: entry for entry in data.entries}
    output = []
    for report in reports:
        entry = entries.get(report["entry_id"])
        if entry is None:
            continue
        laps = {row["lap_number"]: row for row in entry.laps}
        number = report["lap_number"]
        inlap, outlap = laps.get(number), laps.get(number + 1)
        if not inlap or not outlap or inlap.get("lap_end_time_ms") is None:
            continue
        # The provider date can identify a point after the timing line while
        # still in the lane. Verify against the published lane span and lap end.
        offset = report["event_time_ms"] - inlap["lap_end_time_ms"]
        tolerance = min(
            60000, max(20000, ((report.get("lane_duration_s") or 0) + 8) * 1000)
        )
        if abs(offset) > tolerance or report["event_time_ms"] > (
            outlap.get("lap_end_time_ms") or 0
        ):
            continue
        loss = net_loss_from_pair(
            data,
            clean_laps(entry, cutoff),
            inlap,
            outlap,
            cutoff,
            baseline_lap_distance=3,
        )
        if loss:
            output.append(
                {
                    **loss,
                    "entry_id": entry.id,
                    "lane_duration_s": report["lane_duration_s"],
                }
            )
    return output
