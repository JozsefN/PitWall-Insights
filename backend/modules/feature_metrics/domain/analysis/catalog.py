from .models import MetricDefinition

DEFINITIONS: dict[str, MetricDefinition] = {}


def register(group, inputs, rows, *, scope="entry", interpretation="measured"):
    for metric_id, unit, description in rows:
        if metric_id in DEFINITIONS:
            raise RuntimeError("Duplicate analytic metric: " + metric_id)
        DEFINITIONS[metric_id] = MetricDefinition(
            metric_id=metric_id,
            group=group,
            unit=unit,
            description=description,
            required_inputs=inputs,
            scope=scope,
            interpretation=interpretation,
        )


register(
    "laps",
    ["laps"],
    [
        (
            "lap_count",
            "laps",
            "Number of observed completed lap records in the window.",
        ),
        (
            "clean_lap_count",
            "laps",
            "Accurate, non-generated, non-deleted, non-pit laps under clear track status.",
        ),
        ("deleted_lap_count", "laps", "Lap records marked deleted by the source."),
        (
            "best_lap_ms",
            "ms",
            "Fastest clean lap; no fuel, traffic or weather correction.",
        ),
        ("median_lap_ms", "ms", "Median clean lap time."),
        ("mean_lap_ms", "ms", "Arithmetic mean clean lap time."),
        ("lap_std_ms", "ms", "Population standard deviation of clean lap times."),
        ("lap_mad_ms", "ms", "Median absolute deviation of clean lap times."),
        ("lap_cv_pct", "%", "Clean lap standard deviation divided by mean time."),
        ("lap_p90_p10_ms", "ms", "90th minus 10th percentile clean lap time."),
        ("recent_pace_ms", "ms", "Median of the five latest clean laps."),
        (
            "recent_pace_change_ms",
            "ms",
            "Latest five-lap median minus previous five; negative means faster.",
        ),
        ("last_lap_vs_best_ms", "ms", "Last clean lap minus best clean lap."),
        (
            "theoretical_best_lap_ms",
            "ms",
            "Sum of best clean sectors; different laps/conditions may contribute.",
        ),
        (
            "potential_sector_gain_ms",
            "ms",
            "Best actual lap minus theoretical best; not a guaranteed gain.",
        ),
        (
            "sector_sum_mismatch_count",
            "laps",
            "Completed laps whose sector sum differs from lap time by more than 100 ms.",
        ),
    ],
)
for sector in range(1, 4):
    register(
        "laps",
        ["laps"],
        [
            (
                f"sector_{sector}_best_ms",
                "ms",
                f"Best valid sector {sector} on clean laps.",
            ),
            (
                f"sector_{sector}_median_ms",
                "ms",
                f"Median valid sector {sector} on clean laps.",
            ),
            (
                f"sector_{sector}_std_ms",
                "ms",
                f"Population standard deviation of clean sector {sector} times.",
            ),
        ],
    )
register(
    "stints",
    ["laps", "stints"],
    [
        (
            "stint_count",
            "stints",
            "Observed stints represented by selected lap records.",
        ),
        (
            "longest_stint_laps",
            "laps",
            "Largest observed stint in the selected window.",
        ),
        (
            "compound_lap_counts",
            "laps",
            "Observed lap count by tyre compound; includes pit and neutralized laps.",
        ),
        ("stint_pace", "ms", "Per-stint median clean pace, sample count and compound."),
        (
            "tyre_degradation_ms_per_lap",
            "ms/lap",
            "Per-stint OLS pace trend against tyre age, without fuel or track-evolution correction.",
        ),
        ("pit_in_count", "visits", "Observed pit-entry timestamps."),
        ("pit_out_count", "visits", "Observed pit-exit timestamps."),
        (
            "pit_visit_durations_s",
            "s",
            "Matched pit-entry to next pit-exit durations; includes pit-lane travel, not stationary stop time.",
        ),
        ("mean_pit_visit_s", "s", "Mean of matched pit-lane visit durations."),
        ("best_pit_visit_s", "s", "Shortest matched pit-lane visit."),
        (
            "out_lap_delta_ms",
            "ms",
            "Out-lap time minus same-stint clean median, when available.",
        ),
    ],
    interpretation="estimated",
)
register(
    "speed",
    ["car"],
    [
        ("max_speed_kph", "km/h", "Maximum sampled plausible reported speed."),
        ("min_speed_kph", "km/h", "Minimum sampled plausible reported speed."),
        (
            "mean_speed_kph",
            "km/h",
            "Time-weighted mean reported speed over observed intervals.",
        ),
        ("p95_speed_kph", "km/h", "95th percentile of valid reported speed samples."),
        ("speed_std_kph", "km/h", "Standard deviation of sampled speed."),
        (
            "integrated_distance_m",
            "m",
            "Trapezoidal speed integral across bounded, valid sample intervals.",
        ),
        (
            "moving_time_s",
            "s",
            "Observed time above the configured stopped-speed threshold.",
        ),
        (
            "stopped_time_s",
            "s",
            "Observed time at or below the configured stopped-speed threshold.",
        ),
        (
            "max_acceleration_g",
            "g",
            "Maximum plausible sampled longitudinal speed derivative; excludes gaps and spikes.",
        ),
        (
            "max_deceleration_g",
            "g",
            "Magnitude of most negative plausible sampled speed derivative.",
        ),
        (
            "mean_positive_acceleration_g",
            "g",
            "Time-weighted positive longitudinal acceleration.",
        ),
        (
            "mean_braking_deceleration_g",
            "g",
            "Time-weighted deceleration while the brake flag is active.",
        ),
        (
            "specific_braking_energy_j_per_kg",
            "J/kg",
            "Observed decrease in specific kinetic energy while braking; excludes mass, drag and recovery assumptions.",
        ),
    ],
    interpretation="estimated",
)
register(
    "controls",
    ["car"],
    [
        ("mean_throttle_pct", "%", "Time-weighted reported throttle."),
        (
            "full_throttle_pct",
            "%",
            "Share of known throttle time above the configured full-throttle threshold.",
        ),
        (
            "partial_throttle_pct",
            "%",
            "Share of known throttle time between 5% and full-throttle threshold.",
        ),
        (
            "coasting_pct",
            "%",
            "Share of jointly observed time with throttle at most 5% and brake off.",
        ),
        ("braking_pct", "%", "Share of observed brake-flag time with brake active."),
        ("braking_time_s", "s", "Observed brake-active duration."),
        (
            "braking_episode_count",
            "episodes",
            "Contiguous observed brake-active episodes; sampling can miss short episodes.",
        ),
        (
            "mean_braking_episode_s",
            "s",
            "Mean observed duration of contiguous brake episodes.",
        ),
        ("max_braking_episode_s", "s", "Longest observed brake episode."),
        (
            "mean_brake_entry_speed_kph",
            "km/h",
            "Mean sampled speed at observed brake-episode starts.",
        ),
        (
            "mean_brake_release_speed_kph",
            "km/h",
            "Mean sampled speed at observed brake-episode ends.",
        ),
        (
            "brake_throttle_overlap_s",
            "s",
            "Observed time with brake active and throttle above 10%.",
        ),
        (
            "throttle_lift_count",
            "events",
            "Observed transitions from full throttle to at most 5%, excluding gaps.",
        ),
    ],
)
register(
    "powertrain",
    ["car"],
    [
        ("mean_rpm", "rpm", "Time-weighted engine speed."),
        ("max_rpm", "rpm", "Maximum plausible sampled engine speed."),
        ("p95_rpm", "rpm", "95th percentile sampled engine speed."),
        (
            "observed_gear_changes",
            "changes",
            "Sum of observed gear-step magnitudes across continuous valid samples.",
        ),
        (
            "observed_upshifts",
            "changes",
            "Observed upward gear steps; reverse/neutral excluded.",
        ),
        (
            "observed_downshifts",
            "changes",
            "Observed downward gear steps; reverse/neutral excluded.",
        ),
        ("top_gear", "gear", "Largest reported gear in the valid 1–8 range."),
        (
            "reported_drs_open_pct",
            "%",
            "Observed fraction with historical FastF1 DRS codes 10, 12 or 14; not eligibility or regulation compliance.",
        ),
        (
            "reported_drs_activations",
            "activations",
            "Observed transitions to a historical DRS-open code.",
        ),
    ],
)
for gear in range(1, 9):
    register(
        "powertrain",
        ["car"],
        [
            (
                f"gear_{gear}_time_pct",
                "%",
                f"Share of known valid gear time reported in gear {gear}.",
            )
        ],
    )
register(
    "position",
    ["position", "laps", "reference_line"],
    [
        (
            "position_distance_m",
            "m",
            "Sum of plausible XY movements; excludes invalid coordinates and GPS jumps.",
        ),
        (
            "mean_position_speed_kph",
            "km/h",
            "Time-weighted speed derived from XY movement, excluding gaps/jumps.",
        ),
        ("max_position_speed_kph", "km/h", "Maximum plausible XY-derived speed."),
        (
            "max_heading_rate_deg_s",
            "deg/s",
            "Largest plausible path-heading change rate; not chassis yaw or steering angle.",
        ),
        (
            "mean_line_deviation_m",
            "m",
            "Mean distance from a reference racing line, not from a track boundary.",
        ),
        (
            "p95_line_deviation_m",
            "m",
            "95th percentile distance from the reference line.",
        ),
        (
            "max_line_deviation_m",
            "m",
            "Largest observed distance from the reference line after GPS filtering.",
        ),
        (
            "large_line_deviation_time_s",
            "s",
            "Observed time beyond the configured line-distance threshold; not proof of leaving the track.",
        ),
        (
            "reported_offtrack_time_s",
            "s",
            "Source OffTrack flag duration with usable coordinates; source flags can also indicate missing data.",
        ),
        (
            "reported_offtrack_episode_count",
            "episodes",
            "Contiguous source OffTrack episodes with usable coordinates.",
        ),
        (
            "reference_lap_length_m",
            "m",
            "Length of the sampled, closed reference lap polyline.",
        ),
        (
            "max_estimated_lateral_g",
            "g",
            "Geometric lateral acceleration estimate from path curvature; not a vehicle accelerometer measurement.",
        ),
    ],
    interpretation="estimated",
)
register(
    "incidents",
    ["car", "laps", "race_control", "track_status"],
    [
        (
            "rapid_speed_drop_count",
            "events",
            "Observed configured speed drops over short continuous intervals; ordinary braking can satisfy this.",
        ),
        (
            "max_rapid_speed_drop_kph",
            "km/h",
            "Largest observed qualifying short-window drop.",
        ),
        (
            "non_pit_stop_episode_count",
            "episodes",
            "Sustained sampled stops outside known pit visits and neutralized periods.",
        ),
        (
            "non_pit_stop_time_s",
            "s",
            "Duration of qualifying non-pit stopped episodes.",
        ),
        (
            "possible_incident_count",
            "candidates",
            "Rapid slowdown followed by a sustained non-pit stop; never a confirmed crash classification.",
        ),
        (
            "reported_incident_message_count",
            "messages",
            "Source messages mentioning incidents, collisions, spins or a stopped car for this driver.",
        ),
        (
            "reported_track_limit_message_count",
            "messages",
            "Source messages mentioning track limits for this driver.",
        ),
    ],
    interpretation="inferred",
)
register(
    "racing",
    ["laps", "position", "reference_line", "car"],
    [
        (
            "last_reported_position",
            "position",
            "Most recent position on a completed lap in the selected window.",
        ),
        (
            "positions_gained_from_grid",
            "positions",
            "Grid position minus latest completed-lap position; not an on-track overtake count.",
        ),
        (
            "timing_position_gain_count",
            "positions",
            "Positive changes between completed-lap position reports; may include pit cycles/retirements.",
        ),
        (
            "timing_position_loss_count",
            "positions",
            "Negative changes between completed-lap position reports.",
        ),
        (
            "median_lap_gap_to_field_best_ms",
            "ms",
            "Median difference to the fastest clean field lap with the same lap number.",
        ),
        (
            "mean_speed_delta_to_position_kph",
            "km/h",
            "Mean absolute difference between reported and position-derived speeds at aligned observations.",
        ),
        (
            "nearest_car_distance_m",
            "m",
            "Minimum simultaneous interpolated XY separation with fresh data; not a collision detector.",
        ),
        (
            "close_car_time_s",
            "s",
            "Observed sampled time with another fresh car within 30 m; includes non-following proximity.",
        ),
    ],
    interpretation="estimated",
)
register(
    "conditions",
    ["weather", "track_status", "race_control"],
    [
        (
            "mean_air_temp_c",
            "degC",
            "Time-weighted air temperature over covered weather intervals.",
        ),
        ("mean_track_temp_c", "degC", "Time-weighted track temperature."),
        ("min_track_temp_c", "degC", "Minimum observed track temperature."),
        ("max_track_temp_c", "degC", "Maximum observed track temperature."),
        ("mean_humidity_pct", "%", "Time-weighted humidity."),
        ("mean_pressure_mbar", "mbar", "Time-weighted atmospheric pressure."),
        (
            "mean_wind_speed_kph",
            "km/h",
            "Time-weighted wind speed after source-unit conversion.",
        ),
        ("max_wind_speed_kph", "km/h", "Maximum observed wind speed."),
        (
            "mean_wind_direction_deg",
            "deg",
            "Circular mean wind direction weighted by observation duration.",
        ),
        (
            "reported_rain_time_s",
            "s",
            "Weather-covered time with rainfall flag active, not measured rain intensity.",
        ),
        ("clear_track_time_s", "s", "Duration of source track status 1."),
        ("yellow_track_time_s", "s", "Duration of source track status 2."),
        ("safety_car_time_s", "s", "Duration of source track status 4."),
        ("red_flag_time_s", "s", "Duration of source track status 5."),
        ("vsc_time_s", "s", "Duration of source track status 6 or 7."),
        (
            "race_control_message_count",
            "messages",
            "Race-control messages within the selected time window.",
        ),
        (
            "lap_time_deleted_message_count",
            "messages",
            "Race-control messages reporting deleted lap times.",
        ),
    ],
    scope="session",
)
register(
    "quality",
    ["car", "position", "laps"],
    [
        ("car_sample_count", "samples", "Sampled car records used by the analysis."),
        (
            "position_sample_count",
            "samples",
            "Sampled position records used by the analysis.",
        ),
        (
            "car_time_coverage_pct",
            "%",
            "Fraction of the requested time window covered by bounded car-sample intervals.",
        ),
        (
            "position_time_coverage_pct",
            "%",
            "Fraction covered by bounded usable position intervals.",
        ),
        (
            "car_gap_count",
            "gaps",
            "Consecutive car timestamp gaps larger than the configured maximum.",
        ),
        (
            "position_gap_count",
            "gaps",
            "Consecutive position timestamp gaps larger than the configured maximum.",
        ),
        ("largest_car_gap_ms", "ms", "Largest observed internal car timestamp gap."),
        (
            "largest_position_gap_ms",
            "ms",
            "Largest observed internal position timestamp gap.",
        ),
        ("median_car_interval_ms", "ms", "Median car sample interval."),
        ("median_position_interval_ms", "ms", "Median position sample interval."),
        (
            "invalid_speed_sample_count",
            "samples",
            "Missing, non-finite or implausible reported speed samples.",
        ),
        (
            "invalid_position_sample_count",
            "samples",
            "Missing/non-finite or zero XY coordinate pairs.",
        ),
        (
            "position_jump_count",
            "jumps",
            "Continuous XY steps implying speed above the plausibility limit.",
        ),
        (
            "repeated_position_pct",
            "%",
            "Share of continuous usable XY steps with exactly repeated coordinates.",
        ),
    ],
)


def selected_definitions(request):
    unknown = set(request.metric_ids or []) - DEFINITIONS.keys()
    if unknown:
        raise ValueError("Unsupported metric ids: " + ", ".join(sorted(unknown)))
    selected = [
        definition
        for definition in DEFINITIONS.values()
        if (request.groups is None or definition.group in request.groups)
        and (request.metric_ids is None or definition.metric_id in request.metric_ids)
    ]
    if not selected:
        raise ValueError("The metric/group selection is empty")
    return selected
