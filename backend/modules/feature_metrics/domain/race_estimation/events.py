from statistics import median
from .common import event, is_clean, number


def reported_events(data, context, request):
    output = []
    for row in data.race_control:
        t = row["session_time_ms"] + request.assumptions.source_report_delay_ms
        if not data.start_ms <= t <= request.as_of_ms:
            continue
        message = str(row.get("message") or "")
        flag = str(row.get("flag") or "").upper()
        category = str(row.get("category") or "").upper()
        text = message.upper()
        if "RED" in flag:
            kind, severity, title = "red_flag", "warning", "Red flag"
        elif "SAFETY CAR" in text or "VSC" in text or "SAFETYCAR" in category:
            kind, severity, title = "safety_car", "watch", "Safety-car update"
        elif "YELLOW" in flag:
            kind, severity, title = "yellow_flag", "watch", "Yellow flag"
        elif flag == "GREEN" or "GREEN FLAG" in text:
            kind, severity, title = "green_flag", "info", "Green flag"
        elif "TRACK LIMIT" in text or "LEFT THE TRACK" in text:
            kind, severity, title = "track_limits", "info", "Track limits report"
        elif "COLLISION" in text or ("CONTACT" in text and "NO CONTACT" not in text):
            kind, severity, title = "contact_report", "watch", "Race-control contact report"
        elif "DAMAGE" in text or "FRONT WING" in text:
            kind, severity, title = "damage_report", "watch", "Race-control damage report"
        else:
            kind, severity, title = "track_status", "info", "Race-control update"
        entry_id = row.get("session_entry_id") or context.driver_ids.get(
            str(row.get("driver_number"))
        )
        output.append(
            event(
                kind,
                entry_id,
                row["session_time_ms"],
                t,
                title,
                message,
                support=1,
                severity=severity,
                classification="reported",
                evidence={
                    "flag": flag,
                    "category": category,
                    "sector": row.get("sector"),
                    "source": "race_control",
                },
            )
        )
    previous_session_best = None
    own_best = {}
    completed = [
        (lap["lap_end_time_ms"], entry, lap)
        for entry in data.entries
        for lap in entry.laps
        if is_clean(lap)
        and lap.get("lap_end_time_ms") is not None
        and lap["lap_end_time_ms"] <= request.as_of_ms
    ]
    completed.sort(key=lambda item: (item[0], item[1].id))
    for t, entry, lap in completed:
        value = lap["lap_time_ms"]
        prior = own_best.get(entry.id)
        if prior is not None and value < prior and t >= data.start_ms:
            output.append(
                event(
                    "personal_best",
                    entry.id,
                    t,
                    t,
                    "Personal best lap",
                    f"Lap {lap['lap_number']}: {value/1000:.3f} s; {((prior-value)/1000):.3f} s quicker than the previous clean best.",
                    support=0.9,
                    severity="info",
                    classification="observed",
                    evidence={"lap": lap["lap_number"], "lap_time_s": value / 1000},
                )
            )
        if (
            previous_session_best is not None
            and value < previous_session_best
            and t >= data.start_ms
        ):
            output.append(
                event(
                    "session_best",
                    entry.id,
                    t,
                    t,
                    "Session best lap",
                    f"Lap {lap['lap_number']}: {value/1000:.3f} s, among the session's observed clean laps.",
                    support=0.9,
                    severity="info",
                    classification="observed",
                    evidence={"lap": lap["lap_number"], "lap_time_s": value / 1000},
                )
            )
        own_best[entry.id] = min(prior or value, value)
        previous_session_best = min(previous_session_best or value, value)
    for row in context.pits:
        t = row.get("known_at_ms", row["session_time_ms"])
        if not data.start_ms <= t <= request.as_of_ms:
            continue
        entry_id = context.driver_ids.get(row["driver_number"])
        if not entry_id:
            continue
        duration = number(row.get("stop_duration"))
        kind = "stationary" if duration is not None else "pit-lane"
        duration = (
            duration
            if duration is not None
            else number(row.get("lane_duration", row.get("pit_duration")))
        )
        prior = [
            (
                number(p.get("stop_duration"))
                if kind == "stationary"
                else number(p.get("lane_duration", p.get("pit_duration")))
            )
            for p in context.pits
            if p.get("known_at_ms", p["session_time_ms"]) < t
        ]
        prior = [value for value in prior if value is not None and value > 0]
        baseline = median(prior) if len(prior) >= 3 else None
        delta = (
            duration - baseline
            if baseline is not None and duration is not None
            else None
        )
        delayed = delta is not None and delta > max(2, baseline * 0.25)
        output.append(
            event(
                "pit_stop_delay" if delayed else "pit_stop",
                entry_id,
                row["session_time_ms"],
                t,
                "Longer pit visit" if delayed else "Pit visit reported",
                (
                    f"Reported {kind} duration: {duration:.2f} s."
                    + (
                        f" {delta:+.2f} s versus earlier comparable reports."
                        if delta is not None
                        else ""
                    )
                    if duration is not None
                    else "A pit visit is reported."
                ),
                support=0.9,
                severity="watch" if delayed else "info",
                classification="reported",
                evidence={
                    "duration_s": duration,
                    "comparison_delta_s": delta,
                    "duration_kind": kind,
                },
                alternatives=(
                    [
                        "Pit-lane traffic or slow approach",
                        "Repairs or a penalty",
                        "Stationary service delay",
                    ]
                    if delayed
                    else []
                ),
            )
        )
    return output
