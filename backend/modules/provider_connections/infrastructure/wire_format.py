"""Preserve UTC/time-delta types across the isolated FastF1 JSON process boundary."""
from datetime import datetime, timedelta
import math


def pack(value):
    if isinstance(value, dict):
        return {str(k): pack(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [pack(v) for v in value]
    if type(value).__name__ in ("NaTType", "NAType"):
        return None
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, timedelta):
        return {"__duration_ms__": value.total_seconds()*1000}
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return pack(value.item())
    return value


def restore(value):
    if isinstance(value, list):
        return [restore(v) for v in value]
    if isinstance(value, dict):
        if set(value) == {"__datetime__"}:
            return datetime.fromisoformat(value["__datetime__"])
        if set(value) == {"__duration_ms__"}:
            return timedelta(milliseconds=value["__duration_ms__"])
        return {k: restore(v) for k, v in value.items()}
    return value
