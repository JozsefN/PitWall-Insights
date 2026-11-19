"""Shared event-time visibility for analytics and strategy."""

from dataclasses import replace


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
