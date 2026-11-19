from ..race_estimation.common import phase_at


def circuit_flags(data, cutoff):
    """Rebuild the reported flag state at the replay clock, by marshal sector."""
    track_flag = None
    sectors = {}
    for row in sorted(data.race_control, key=lambda item: item["session_time_ms"]):
        if row["session_time_ms"] > cutoff:
            break
        flag = str(row.get("flag") or "").strip().upper().replace("_", " ")
        scope = str(row.get("scope") or "").lower()
        sector = row.get("sector")
        if scope == "sector" and isinstance(sector, int) and sector > 0:
            if flag in ("YELLOW", "DOUBLE YELLOW", "RED"):
                sectors[sector] = flag
            elif flag in ("GREEN", "CLEAR"):
                sectors.pop(sector, None)
        elif scope == "track" and flag in (
            "YELLOW",
            "DOUBLE YELLOW",
            "RED",
            "GREEN",
            "CLEAR",
            "CHEQUERED",
        ):
            track_flag = flag
            if flag in ("GREEN", "CLEAR", "CHEQUERED"):
                sectors.clear()
    phase = phase_at(data.track_status, cutoff)
    if track_flag != "CHEQUERED":
        track_flag = {
            "4": "SAFETY CAR",
            "5": "RED",
            "6": "VIRTUAL SAFETY CAR",
            "7": "VSC ENDING",
        }.get(phase, track_flag)
    # An aggregate yellow can describe a local flag with no known spatial footprint.
    return {
        "track_flag": track_flag,
        "sectors": [
            {"number": sector, "flag": sectors[sector]} for sector in sorted(sectors)
        ],
        "unlocated_caution": phase == "2"
        and not sectors
        and track_flag not in ("YELLOW", "DOUBLE YELLOW", "RED", "CHEQUERED"),
    }
