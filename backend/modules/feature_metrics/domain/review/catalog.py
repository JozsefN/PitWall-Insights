"""Stable output paths for building panels and querying review components."""

COMPONENTS = {
    "drivers": {
        "best_clean_lap_s": (
            "s",
            "derived",
            "Minimum eligible completed lap time per driver.",
        ),
        "qualifying[].lap_time_s": (
            "s",
            "reported",
            "Final OpenF1 per-phase qualifying result.",
        ),
        "qualifying[].provider_colours": (
            "codes",
            "reported",
            "Native categorical segments associated with a uniquely matched lap.",
        ),
    },
    "segments": {
        "laps[].segments[].time_s": (
            "s",
            "estimated",
            "Difference between interpolated crossing clocks on equal-distance bins.",
        ),
        "laps[].segments[].delta_to_best_s": (
            "s",
            "estimated",
            "Segment time minus fastest loaded comparison segment.",
        ),
        "laps[].segments[].delta_to_prior_median_s": (
            "s",
            "estimated",
            "Segment time minus prior selected same-driver segment median.",
        ),
        "laps[].segments[].min_speed_kph": (
            "km/h",
            "derived",
            "Minimum sampled speed inside the estimated crossing interval.",
        ),
        "laps[].segments[].mean_throttle_pct": (
            "%",
            "derived",
            "Arithmetic mean of valid throttle samples.",
        ),
        "laps[].segments[].brake_sample_pct": (
            "%",
            "derived",
            "Binary brake-on sample fraction inside the segment.",
        ),
    },
    "radio": {
        "clips[]": (
            "reports",
            "reported",
            "Timestamped published recording links for the selected drivers.",
        )
    },
    "racecraft": {
        "close_following_threshold_s": (
            "s",
            "assumption",
            "Maximum timing headway counted as close following by the battle detector.",
        ),
        "passes[]": (
            "events",
            "estimated",
            "Corroborated provider position changes with a held order swap and pit/phase exclusions.",
        ),
        "battles[].active_battle": (
            "flag",
            "derived",
            "At least three adjacent timing reports over eight seconds with sustained close headway.",
        ),
        "battles[].consistent_closing": (
            "flag",
            "derived",
            "At least four reports over twelve seconds with consistent gap reduction.",
        ),
        "battles[].pace_advantage_s_per_lap": (
            "s/lap",
            "derived",
            "Ahead median recent lap time less follower median recent lap time.",
        ),
    },
    "pace": {
        "drivers[].median_pace_s": (
            "s",
            "derived",
            "Median of the latest five clean same-stint laps.",
        ),
        "drivers[].faster_observed_pace_s": (
            "s",
            "derived",
            "Lower empirical quartile of recent comparable clean laps.",
        ),
        "drivers[].traffic_pace_s": (
            "s",
            "derived",
            "Median among at least two observed traffic-heavy laps in the recent stint.",
        ),
        "drivers[].observed_trend_s_per_lap": (
            "s/lap",
            "derived",
            "Median pairwise clean-lap slope.",
        ),
        "drivers[].fuel_scenario_trend_s_per_lap": (
            "s/lap",
            "scenario",
            "Observed trend plus assumed fuel burn times time sensitivity.",
        ),
        "track_evolution.pace_change_s_per_min": (
            "s/min",
            "estimated",
            "Median pace change with matched driver, compound, tyre age, dry flag and track temperature.",
        ),
        "practice_profiles[]": (
            "runs",
            "derived",
            "Observed dry, clean, consecutive practice runs with at least five timed laps.",
        ),
        "field_projection[]": (
            "s",
            "scenario",
            "Fresh leader gap plus horizon times recent pace and any explicit fuel scenario.",
        ),
        "lapped_traffic_scenarios[]": (
            "s",
            "scenario",
            "Constant mean progress catch time and reference shape sensitivity at the projected catch.",
        ),
    },
    "pit": {
        "net_green_pit_loss.median_s": (
            "s",
            "estimated",
            "Median paired in/out excess over neighboring clean laps from eligible circuit sessions.",
        ),
        "pit_lane_duration.median_s": (
            "s",
            "derived",
            "Median of native completed lane durations.",
        ),
        "stationary_service_duration.median_s": (
            "s",
            "derived",
            "Median of native completed stationary durations.",
        ),
        "exit_scenarios[]": (
            "s",
            "scenario",
            "Current gap plus net pit loss with the other timed drivers held fixed.",
        ),
        "rival_windows[].position_flip_scenario": (
            "flag",
            "scenario",
            "Positive current pit margin and nonpositive margin under a normal rival stop.",
        ),
    },
    "incidents": {
        "reports[]": (
            "reports",
            "reported",
            "Race-control wording and associated driver identifiers.",
        ),
        "report_counts[]": (
            "reports",
            "derived",
            "Count of visible reports by category and driver.",
        ),
        "post_report_pace[].pace_change_s": (
            "s",
            "derived",
            "Difference between same-stint clean medians surrounding a report.",
        ),
    },
    "weather": {
        "timeline[]": (
            "reports",
            "reported",
            "Circuit-level wind, temperature and rain-flag observations.",
        ),
        "rainfall_mm": (
            "mm",
            "unavailable",
            "Requires an external quantitative precipitation feed.",
        ),
    },
    "flags": {
        "track_flag": (
            "flag",
            "reported",
            "Track-wide race-control flag or reported neutralisation at the cutoff.",
        ),
        "sectors[]": (
            "marshal sector",
            "reported",
            "Active sector flags. A registered sector polygon is required to draw a local tint.",
        ),
    },
    "surface": {
        "zones[]": (
            "m",
            "supplied",
            "Survey polygons from a registered, owned strategy context.",
        ),
        "cars[].inside_track_clearance_m": (
            "m",
            "estimated",
            "Signed distance to a registered surface, subject to position uncertainty.",
        ),
        "cars[].nearest_recovery_m": (
            "m",
            "estimated",
            "Straight-line distance to mapped recovery access, subject to coordinate uncertainty.",
        ),
    },
}


def component_catalog():
    return [
        {
            "group": group,
            "path": path,
            "unit": unit,
            "method": method,
            "formula": formula,
        }
        for group, definitions in COMPONENTS.items()
        for path, (unit, method, formula) in definitions.items()
    ]
