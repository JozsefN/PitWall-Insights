import numpy as np
from .common import car_arrays, numeric, stat, weighted_mean, percentage, episodes


def calculate_speed(data, request, result):
    for entry in data.entries:
        if not entry.car:
            result.missing(
                "speed",
                entry.id,
                "Car telemetry is not materialized for this selection.",
            )
            continue
        times, duration, speed, _, brake = car_arrays(entry, data, request)
        n = int(np.sum(np.isfinite(speed)))
        observed = float(np.sum(duration[np.isfinite(speed)]))
        support = min(1, observed / max(1, (data.end_ms - data.start_ms) / 1000))

        def put(key, value, confidence=None):
            result.put(
                key,
                value,
                entry.id,
                n=n,
                confidence=support if confidence is None else min(support, confidence),
            )

        for key, operation in (
            ("max_speed_kph", "max"),
            ("min_speed_kph", "min"),
            ("p95_speed_kph", "p95"),
            ("speed_std_kph", "std"),
        ):
            put(key, stat(speed, operation))
        put("mean_speed_kph", weighted_mean(speed, duration))
        dt = np.diff(times) / 1000
        ds = np.diff(speed) / 3.6
        valid = (
            (dt > 0)
            & (dt <= request.options.max_sample_gap_ms / 1000)
            & np.isfinite(ds)
        )
        acceleration = np.full(len(dt), np.nan)
        acceleration[valid] = ds[valid] / dt[valid] / 9.80665
        # Telemetry spikes must not become alleged extreme vehicle forces.
        valid &= np.abs(acceleration) <= 10
        acceleration[~valid] = np.nan
        distance = (speed[:-1] + speed[1:]) / 2 / 3.6 * dt
        put(
            "integrated_distance_m",
            float(np.sum(distance[valid])) if np.any(valid) else None,
            0.9,
        )
        known = np.isfinite(speed)
        put(
            "moving_time_s",
            float(
                np.sum(duration[known & (speed > request.options.stopped_speed_kph)])
            ),
        )
        put(
            "stopped_time_s",
            float(
                np.sum(duration[known & (speed <= request.options.stopped_speed_kph)])
            ),
        )
        put("max_acceleration_g", stat(acceleration[acceleration > 0], "max"), 0.75)
        put("max_deceleration_g", stat(-acceleration[acceleration < 0], "max"), 0.75)
        put(
            "mean_positive_acceleration_g",
            weighted_mean(
                np.where(acceleration > 0, acceleration, np.nan), np.where(valid, dt, 0)
            ),
            0.75,
        )
        braking = valid & (brake[:-1] == 1) & (acceleration < 0)
        put(
            "mean_braking_deceleration_g",
            weighted_mean(
                np.where(braking, -acceleration, np.nan), np.where(valid, dt, 0)
            ),
            0.75,
        )
        energy = 0.5 * ((speed[:-1] / 3.6) ** 2 - (speed[1:] / 3.6) ** 2)
        put(
            "specific_braking_energy_j_per_kg",
            float(np.sum(energy[braking])) if np.any(valid) else None,
            0.65,
        )


def calculate_controls(data, request, result):
    for entry in data.entries:
        if not entry.car:
            result.missing(
                "controls",
                entry.id,
                "Car telemetry is not materialized for this selection.",
            )
            continue
        times, duration, speed, throttle, brake = car_arrays(entry, data, request)

        def put(key, value):
            result.put(
                key,
                value,
                entry.id,
                n=len(entry.car),
                confidence=min(1, len(entry.car) / 20),
            )

        known_throttle = np.isfinite(throttle)
        known_brake = np.isfinite(brake)
        put("mean_throttle_pct", weighted_mean(throttle, duration))
        put(
            "full_throttle_pct",
            percentage(
                throttle >= request.options.full_throttle_pct, duration, known_throttle
            ),
        )
        put(
            "partial_throttle_pct",
            percentage(
                (throttle > 5) & (throttle < request.options.full_throttle_pct),
                duration,
                known_throttle,
            ),
        )
        put(
            "coasting_pct",
            percentage(
                (throttle <= 5) & (brake == 0), duration, known_throttle & known_brake
            ),
        )
        put("braking_pct", percentage(brake == 1, duration, known_brake))
        put(
            "braking_time_s",
            float(np.sum(duration[brake == 1])) if np.any(known_brake) else None,
        )
        runs = episodes(brake == 1, times, duration)
        put("braking_episode_count", len(runs) if np.any(known_brake) else None)
        put("mean_braking_episode_s", stat([length for _, _, length in runs], "mean"))
        put("max_braking_episode_s", stat([length for _, _, length in runs], "max"))
        put(
            "mean_brake_entry_speed_kph",
            stat([speed[start] for start, _, _ in runs], "mean"),
        )
        put(
            "mean_brake_release_speed_kph",
            stat([speed[end - 1] for _, end, _ in runs], "mean"),
        )
        put(
            "brake_throttle_overlap_s",
            (
                float(np.sum(duration[(brake == 1) & (throttle > 10)]))
                if np.any(known_brake & known_throttle)
                else None
            ),
        )
        continuous = (np.diff(times) > 0) & (
            np.diff(times) <= request.options.max_sample_gap_ms
        )
        put(
            "throttle_lift_count",
            (
                int(
                    np.sum(
                        (throttle[:-1] >= request.options.full_throttle_pct)
                        & (throttle[1:] <= 5)
                        & continuous
                    )
                )
                if np.any(known_throttle)
                else None
            ),
        )


def calculate_powertrain(data, request, result):
    for entry in data.entries:
        if not entry.car:
            result.missing(
                "powertrain",
                entry.id,
                "Car telemetry is not materialized for this selection.",
            )
            continue
        times, duration, *_ = car_arrays(entry, data, request)
        rpm = numeric(entry.car, "rpm")
        rpm[(rpm < 0) | (rpm > 20000)] = np.nan
        gear = numeric(entry.car, "gear")
        gear[~np.isin(gear, np.arange(1, 9))] = np.nan
        drs = numeric(entry.car, "drs_state")
        known = np.isfinite(drs)
        opened = np.isin(drs, [10, 12, 14])

        def put(key, value):
            result.put(
                key,
                value,
                entry.id,
                n=len(entry.car),
                confidence=min(1, len(entry.car) / 20),
            )

        put("mean_rpm", weighted_mean(rpm, duration))
        put("max_rpm", stat(rpm, "max"))
        put("p95_rpm", stat(rpm, "p95"))
        continuous = (np.diff(times) > 0) & (
            np.diff(times) <= request.options.max_sample_gap_ms
        )
        changes = np.diff(gear)
        valid = continuous & np.isfinite(changes)
        put(
            "observed_gear_changes",
            int(np.sum(np.abs(changes[valid]))) if np.any(np.isfinite(gear)) else None,
        )
        put(
            "observed_upshifts",
            (
                int(np.sum(changes[valid & (changes > 0)]))
                if np.any(np.isfinite(gear))
                else None
            ),
        )
        put(
            "observed_downshifts",
            (
                int(np.sum(-changes[valid & (changes < 0)]))
                if np.any(np.isfinite(gear))
                else None
            ),
        )
        put("top_gear", stat(gear, "max"))
        put("reported_drs_open_pct", percentage(opened, duration, known))
        put(
            "reported_drs_activations",
            (
                int(
                    np.sum(
                        ~opened[:-1] & opened[1:] & continuous & known[:-1] & known[1:]
                    )
                )
                if np.any(known)
                else None
            ),
        )
        for number in range(1, 9):
            put(
                f"gear_{number}_time_pct",
                percentage(gear == number, duration, np.isfinite(gear)),
            )
