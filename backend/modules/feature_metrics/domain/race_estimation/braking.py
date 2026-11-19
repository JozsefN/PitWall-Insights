"""Evidence from brake-on samples and vehicle speed. No wheel-speed inference."""

PLATEAU_DURATION_MS = 1000
PLATEAU_SAMPLE_COUNT = 4


def plateau_step(previous_speed, speed, brake, throttle):
    return (
        brake
        and speed >= 100
        and (throttle or 0) < 10
        and abs(speed - previous_speed) <= 1
    )


def first_braking_plateau(samples):
    previous = None
    start, count = None, 0
    for row in samples:
        stamp = row["session_time_ms"]
        if (
            previous is not None
            and 0 < stamp - previous["session_time_ms"] <= 1500
            and row["lap_id"] == previous["lap_id"]
            and plateau_step(
                previous["speed_kph"],
                row["speed_kph"],
                row["brake_on"] is True,
                row["throttle_pct"],
            )
        ):
            if start is None:
                start, count = previous["session_time_ms"], 1
            count += 1
            if stamp - start >= PLATEAU_DURATION_MS and count >= PLATEAU_SAMPLE_COUNT:
                return stamp
        else:
            start, count = None, 0
        previous = row
    return None
