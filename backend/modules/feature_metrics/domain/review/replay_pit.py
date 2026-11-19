"""Same-circuit net pit loss and race gaps for replay planning."""

from statistics import median

from ..strategy.common import clean_laps
from ..strategy.pits import empirical_pit_losses
from .pace import rain_state
from .pit import benchmark, native_net_losses
from .pit_sector_loss import session_pit_sectors


def archive_stop_ratio(history, circuit, phase):
    comparable = [row for row in history if {"green", phase} <= row["phases"].keys()]
    local = [row for row in comparable if row["circuit"] == circuit]
    if len(comparable) < 3 and not local:
        return None

    def ratio(cohort):
        return median(
            row["phases"][phase]["median_s"] / row["phases"]["green"]["median_s"]
            for row in cohort
        )

    if len(comparable) < 3:
        return ratio(local), {
            "scope": "same_circuit_sector_archive",
            "samples": len(local),
        }
    pooled = ratio(comparable)
    basis = {"scope": "pooled_sector_archive", "samples": len(comparable)}
    if local:
        # A small same-circuit sample inherits the equivalent of two pooled races.
        pooled = (len(local) * ratio(local) + 2 * pooled) / (len(local) + 2)
        basis.update(scope="circuit_adjusted_sector_archive", local_samples=len(local))
    return pooled, basis


def pit_model(sessions, prior=(), before_epoch=0, circuit=None, sector_archive=()):
    green_losses, green_lanes = [], []
    sector_losses = {"green": [], "sc": [], "vsc": []}
    neutral_ratios = {"sc": [], "vsc": []}
    for data, reports in sessions:
        cutoff = data.end_ms
        losses = native_net_losses(data, cutoff, reports) or empirical_pit_losses(
            data, cutoff
        )
        dry = [
            {**row, "session_id": data.session_id}
            for row in losses
            if rain_state(data, row["stop_lap_end_ms"]) is False
        ]
        green_losses.extend(dry)
        green_lanes.extend(row for row in dry if row.get("lane_duration_s") is not None)
        for row in session_pit_sectors(data, reports) if reports else ():
            if rain_state(data, row["stop_lap_end_ms"]) is False:
                sector_losses[row["phase"]].append(
                    {**row, "session_id": data.session_id}
                )
        for entry in data.entries:
            clean = clean_laps(entry, cutoff)
            if len(clean) < 3:
                continue
            clean_pace = median(row["lap_time_ms"] for row in clean)
            for row in entry.laps:
                status = row.get("track_status")
                if (
                    status not in ("4", "6")
                    or not row.get("lap_time_ms")
                    or row.get("lap_end_time_ms") is None
                    or row["lap_end_time_ms"] > cutoff
                    or row.get("pit_in_time_ms") is not None
                    or row.get("pit_out_time_ms") is not None
                ):
                    continue
                if rain_state(data, row["lap_end_time_ms"]) is False:
                    ratio = row["lap_time_ms"] / clean_pace
                    if 1 < ratio <= 3:
                        neutral_ratios["sc" if status == "4" else "vsc"].append(ratio)
    result = benchmark(green_losses, "net_loss_s")
    history = [row for row in sector_archive if row["available_after"] < before_epoch]
    local_green = [
        row for row in history if row["circuit"] == circuit and "green" in row["phases"]
    ]
    measured = benchmark(sector_losses["green"], "net_loss_s")
    green_basis = "whole_laps"
    if measured["median_s"] is not None:
        result, green_basis = measured, "timing_sectors"
    elif local_green:
        result = {
            "median_s": median(
                row["phases"]["green"]["median_s"] for row in local_green
            ),
            "sample_count": sum(
                row["phases"]["green"]["samples"] for row in local_green
            ),
            "robust_scatter_s": median(
                row["phases"]["green"].get("scatter_s", 0) for row in local_green
            ),
            "session_ids": [f"openf1:session:{row['race']}" for row in local_green],
        }
        green_basis = "same_circuit_timing_archive"
    lane = benchmark(green_lanes, "lane_duration_s")["median_s"]
    green = result["median_s"]
    discount = {"sc": None, "vsc": None}
    discount_basis = {}
    bypass = [
        row["lane_duration_s"] - row["net_loss_s"]
        for row in green_lanes
        if -15 <= row["lane_duration_s"] - row["net_loss_s"] <= 50
    ]
    bypass_s = median(bypass) if len(bypass) >= 3 else None
    if bypass_s is not None and green is not None and bypass_s > 0:
        # The lane bypasses (lane minus net loss) seconds of racing at green pace.
        # A longer on-track traversal saves that extra time during a stop.
        for phase, ratios in neutral_ratios.items():
            if len(ratios) >= 3:
                ratio = median(ratios)
                discount_basis[phase] = {
                    "scope": "local_laps",
                    "samples": len(ratios),
                    "pace_ratio": ratio,
                }
            else:
                historic = [
                    row
                    for row in prior
                    if row["available_after"] < before_epoch and phase in row["phases"]
                ]
                local = [row for row in historic if row["circuit"] == circuit]
                same_circuit = len(local) >= 2
                eligible = local if same_circuit else historic
                if len(eligible) < (2 if same_circuit else 3):
                    continue
                ratio = median(row["phases"][phase]["ratio"] for row in eligible)
                discount_basis[phase] = {
                    "scope": (
                        "same_circuit_archive" if same_circuit else "pooled_archive"
                    ),
                    "samples": len(eligible),
                    "pace_ratio": ratio,
                }
            discount[phase] = min(green, bypass_s * (ratio - 1))
    if green is not None:
        for phase in discount:
            current = benchmark(sector_losses[phase], "net_loss_s")
            if current["median_s"] is not None and green_basis != "whole_laps":
                discount[phase] = max(0, green - current["median_s"])
                discount_basis[phase] = {
                    "scope": "timing_sectors",
                    "samples": current["sample_count"],
                }
                continue
            archived = archive_stop_ratio(history, circuit, phase)
            if archived:
                ratio, basis = archived
                discount[phase] = min(green, max(0, green * (1 - ratio)))
                discount_basis[phase] = basis
    return {
        **result,
        "matched_lane_s": lane,
        "green_basis": green_basis,
        "discount_s": discount,
        "discount_basis": discount_basis,
        "neutral_lap_samples": {key: len(rows) for key, rows in neutral_ratios.items()},
    }
