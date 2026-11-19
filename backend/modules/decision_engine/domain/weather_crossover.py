"""Short-horizon tyre choices driven by observed sector deltas and timed rain scenarios."""

from statistics import median

from modules.feature_metrics.domain.review.pace import rain_state
from modules.feature_metrics.domain.review.replay_sectors import (
    FAMILIES,
    FRESH_WINDOW_MS,
    PEER_WINDOW_MS,
    family,
)
from modules.feature_metrics.domain.strategy.common import mad


def field_comparison(timing, after_ms=0, excluded=(), warmup=None, slick=None):
    """Compare each scout with same-sector peers crossing nearby in time."""
    cutoff = timing.cutoff
    offsets = timing.offsets(cutoff)
    warmup = warmup or {}

    def regular_time(row):
        cold = (
            warmup.get((row.family, row.sector), {}).get("loss_s", 0)
            if row.outlap
            else 0
        )
        return row.seconds - offsets.get((row.driver, row.sector), 0) - cold

    comparisons = {}
    for i, first in enumerate(FAMILIES):
        for second in FAMILIES[i + 1 :]:
            changes, sources, controls = [], set(), set()
            for sector, rows in timing.splits.items():
                recent = {
                    row.driver: row
                    for row in rows
                    if row.end >= max(after_ms, cutoff - FRESH_WINDOW_MS)
                    and row.driver not in excluded
                    and (
                        slick is None or row.family != "SLICK" or row.compound == slick
                    )
                }
                base = [row for row in recent.values() if row.family == first]
                samples = [row for row in recent.values() if row.family == second]
                deltas = []
                for scout in samples:
                    peers = [
                        row
                        for row in base
                        if abs(row.end - scout.end) <= PEER_WINDOW_MS
                    ]
                    if not peers:
                        continue
                    # Use freshest local references on either side of each crossing.
                    matched = sorted(peers, key=lambda row: abs(row.end - scout.end))[
                        :4
                    ]
                    reference = median(regular_time(row) for row in matched)
                    deltas.append(reference - regular_time(scout))
                    sources.add(scout.driver)
                    controls.update(row.driver for row in matched)
                if deltas:
                    changes.append(
                        {
                            "sector": sector,
                            "gain_s": median(deltas),
                            "spread_s": max(0.35, mad(deltas) or 0.0),
                            "comparisons": len(deltas),
                        }
                    )
            if changes:
                comparisons[first, second] = (changes, len(controls), len(sources))
    return comparisons


def comparison_for(comparisons, source, target):
    if (source, target) in comparisons:
        return comparisons[source, target]
    opposite = comparisons.get((target, source))
    if opposite:
        rows, a, b = opposite
        return [{**row, "gain_s": -row["gain_s"]} for row in rows], b, a
    return [], 0, 0


def archived_gain(archive, before_epoch, source, target, intensity):
    records = []
    for row in archive:
        if row["available_after"] >= before_epoch:
            continue
        lookup = row["conditions"].get(intensity, {})
        value = lookup.get(f"{source}:{target}")
        reverse = lookup.get(f"{target}:{source}")
        if value is not None or reverse is not None:
            records.append(value if value is not None else -reverse)
    if len(records) < 2:
        return None
    return median(records), max(2.5, mad(records) or 0), len(records)


def rain_prior(archive, before_epoch, source, target, intensity):
    value = archived_gain(archive, before_epoch, source, target, intensity)
    if (
        value is None
        and intensity == "heavy"
        and {source, target} == {"SLICK", "INTERMEDIATE"}
    ):
        value = archived_gain(archive, before_epoch, source, target, "rain")
    if value is None and intensity == "heavy" and {source, target} == {"SLICK", "WET"}:
        slick = archived_gain(archive, before_epoch, source, "INTERMEDIATE", "rain")
        wet = archived_gain(archive, before_epoch, "INTERMEDIATE", target, "heavy")
        if slick is not None and wet is not None:
            value = slick[0] + wet[0], slick[1] + wet[1], min(slick[2], wet[2])
    return value


def rain_crossover(
    data,
    timing,
    remaining,
    pit,
    incident,
    excluded,
    archive=(),
    before_epoch=0,
    forecast=None,
    warmup=None,
):
    observed = rain_state(data, timing.cutoff)
    current = {
        key: value for key, value in timing.current.items() if key not in excluded
    }
    counts = dict.fromkeys(FAMILIES, 0)
    for compound in current.values():
        counts[family(compound)] += 1
    active = (
        observed is True
        or counts["INTERMEDIATE"] + counts["WET"] > 0
        or forecast is not None
    )
    grip = timing.slick_traction() if active else []
    wetting = observed is True and (
        len(grip) >= 2 or any(row["slowdown_s"] >= 2.5 for row in grip)
    )
    result = {
        "active": active,
        "rain_reported": observed,
        "field": counts,
        "forecast": forecast,
        "grip": grip,
        "decisions": {},
    }
    if not active or not remaining or incident["phase"] in (None, "5"):
        return result
    last_change = 0
    previous = None
    for row in data.weather:
        report = row.get("rainfall")
        if row["session_time_ms"] > timing.cutoff or report not in (True, False):
            continue
        if previous is not None and report != previous:
            last_change = row["session_time_ms"]
        previous = report
    warmup = warmup or {}
    comparisons = field_comparison(
        timing, max(0, last_change - 25_000), excluded, warmup
    )
    matched_slicks = (
        {
            compound: field_comparison(
                timing, max(0, last_change - 25_000), excluded, warmup, slick=compound
            )
            for compound in set(current.values())
            if family(compound) == "SLICK"
        }
        if comparisons
        else {}
    )
    horizon = min(5, remaining)
    green = pit["median_s"]
    phase = {"4": "sc", "6": "vsc"}.get(incident["phase"])
    now = green - (pit["discount_s"].get(phase) or 0) if green is not None else None
    closed = incident["pit_entry_closed"]
    laps_by_driver = {
        entry.id: next(
            (
                row["lap_time_ms"] / 1000
                for row in reversed(entry.laps)
                if row.get("lap_end_time_ms") is not None
                and row["lap_end_time_ms"] <= timing.cutoff
                and 40_000 <= (row.get("lap_time_ms") or 0) <= 240_000
            ),
            None,
        )
        for entry in data.entries
    }
    field_lap = (
        median([value for value in laps_by_driver.values() if value])
        if any(laps_by_driver.values())
        else 90
    )
    for driver, compound in current.items():
        source = family(compound)
        source_splits = timing.by_driver[driver]
        lookup = {}
        for sample in source_splits:
            if (
                sample.family == source
                and timing.cutoff - sample.end <= 420_000
                and not sample.outlap
            ):
                lookup[sample.sector] = sample.seconds
        lap_s = (
            sum(lookup.values())
            if len(lookup) == 3
            else laps_by_driver.get(driver) or field_lap
        )
        latest, outlap, _ = timing.latest[driver]
        elapsed_s = max(0, (timing.cutoff - latest["lap_start_time_ms"]) / 1000)
        if latest.get("lap_end_time_ms") is not None:
            elapsed_s = max(0, (timing.cutoff - latest["lap_end_time_ms"]) / 1000)
        arrival = max(0, lap_s - elapsed_s)
        options = []
        for target in FAMILIES:
            if target == source:
                continue
            sections, base_count, scouts = comparison_for(comparisons, source, target)
            specific = comparison_for(matched_slicks.get(compound, {}), source, target)
            exact_compound = (
                source == "SLICK"
                and specific[1] >= 2
                and len(specific[0]) >= len(sections)
            )
            if exact_compound:
                sections, base_count, scouts = specific
            if not sections and not forecast and not (wetting and source == "SLICK"):
                continue
            field_gain = sum(section["gain_s"] for section in sections)
            # Missing sectors add no unobserved gain to the decision.
            spread = (
                sum(section["spread_s"] for section in sections)
                + (3 - len(sections)) * 0.75
            )
            prior = (
                rain_prior(archive, before_epoch, source, target, forecast["intensity"])
                if forecast
                else None
            )
            observed_prior = (
                rain_prior(archive, before_epoch, source, target, "rain")
                if not sections and wetting and source == "SLICK"
                else None
            )
            if not sections and prior is None and observed_prior is None:
                continue
            support = bool(
                sections
                and (
                    scouts >= 2
                    and (base_count >= 2 or len(sections) >= 2)
                    or len(sections) >= 2
                    and base_count >= 2
                )
            )
            forecast_weight = forecast["probability_pct"] / 100 if forecast else 0
            step = lap_s * 1000
            race_gains = []
            for offset in range(horizon):
                lap_start = timing.cutoff + arrival * 1000 + offset * step
                overlap = (
                    max(
                        0,
                        min(lap_start + step, forecast["ends_at_ms"])
                        - max(lap_start, forecast["starts_at_ms"]),
                    )
                    if prior
                    else 0
                )
                now_gain = field_gain
                # Before the first crossover, pace of the other tyre is uncertain prior to the rain.
                if observed_prior:
                    now_gain = observed_prior[0]
                elif not sections and prior:
                    dry = archived_gain(archive, before_epoch, source, target, "dry")
                    now_gain = dry[0] if dry else -prior[1]
                    if source == "SLICK":
                        now_gain = min(0.0, now_gain)
                if overlap and prior:
                    expected = forecast_weight * overlap / step
                    now_gain = (1 - expected) * now_gain + expected * prior[0]
                race_gains.append(now_gain)
            # Hold the current compound for the comparison horizon and compare one stop now or next lap.
            # If the scenario ends during the horizon, the normal-condition gains apply again.
            spread = max(
                spread,
                prior[1] * forecast_weight if prior else 0,
                observed_prior[1] if observed_prior else 0,
            )
            thermal = [
                warmup[target, sector]
                for sector in (2, 3)
                if (target, sector) in warmup
            ]
            warmup_s = sum(row["loss_s"] for row in thermal) if thermal else None
            extra = (warmup_s or 0) if pit.get("green_basis") != "whole_laps" else 0.0
            box = (
                sum(race_gains) - now - extra
                if now is not None and not closed
                else None
            )
            wait = (
                sum(race_gains[1:]) - green - extra
                if green is not None and horizon > 1
                else None
            )
            projected = bool(prior and not support)
            options.append(
                {
                    "target": target,
                    "sectors": sections,
                    "scouts": scouts,
                    "references": base_count,
                    "reference_compound": compound if exact_compound else None,
                    "gain_s_lap": field_gain if sections else None,
                    "box_s": box,
                    "wait_s": wait,
                    "earlier_switch_s": (
                        box - wait if box is not None and wait is not None else None
                    ),
                    "warmup_s": warmup_s,
                    "warmup_included": bool(
                        thermal and pit.get("green_basis") != "whole_laps"
                    ),
                    "spread_s": spread,
                    "historical_races": (
                        prior[2]
                        if prior
                        else observed_prior[2] if observed_prior else 0
                    ),
                    "forecast_driven": projected,
                    "supported": support
                    or bool(prior and forecast_weight >= 0.65)
                    or observed_prior is not None,
                }
            )
        options.sort(
            key=lambda row: (
                row["supported"],
                max(
                    value
                    for value in (row["box_s"], row["wait_s"], -1e6)
                    if value is not None
                ),
            ),
            reverse=True,
        )
        # Every circulating driver is assessed against the whole field, regardless of rivalry.
        chosen = options[0] if options else None
        action = "observe"
        if closed:
            action = "closed"
        elif outlap and latest.get("lap_end_time_ms") is None:
            action = "outlap"
        elif chosen and chosen["supported"] and chosen["box_s"] is not None:
            edge = chosen["spread_s"]
            box, wait = chosen["box_s"], chosen["wait_s"] or 0
            if box > max(0, wait) + edge:
                action = "forecast_box" if chosen["forecast_driven"] else "box"
            elif wait > max(0, box) + edge:
                action = "wait"
            elif max(box, wait) <= -edge and (
                len(chosen["sectors"]) >= 2 or chosen["forecast_driven"]
            ):
                action = "hold"
        result["decisions"][driver] = {
            "entry_id": driver,
            "compound": compound,
            "action": action,
            "target": chosen["target"] if chosen else None,
            "options": options,
            "laps": horizon,
            "arrival_s": arrival,
            "pit_cost_s": now,
        }
    return result
