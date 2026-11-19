"""Convert timestamped source reports onto the canonical session clock."""

from datetime import datetime


def timed_rows(rows, origin):
    if origin is None:
        return []
    output = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        try:
            stamp = datetime.fromisoformat(str(row["date"]).replace("Z", "+00:00"))
            elapsed = round((stamp - origin).total_seconds() * 1000)
        except (ValueError, KeyError, TypeError, OverflowError):
            continue
        car = row.get("driver_number")
        output.append(
            {
                **row,
                "session_time_ms": elapsed,
                "driver_number": str(car) if car is not None else None,
            }
        )
    return sorted(output, key=lambda row: row["session_time_ms"])
