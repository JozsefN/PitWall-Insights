"""Only decision-relevant strategy primitives, with explicit formula and consumer."""

from pydantic import BaseModel


class Definition(BaseModel):
    metric_id: str
    group: str
    scope: str
    unit: str
    formula: str
    use: str
    requires: list[str]
    limitations: str


DEFINITIONS: dict[str, Definition] = {}


def group(name, scope, requires, limitations, rows):
    for key, unit, formula, use in rows:
        if key in DEFINITIONS:
            raise RuntimeError("Duplicate strategy metric")
        DEFINITIONS[key] = Definition(
            metric_id=key,
            group=name,
            scope=scope,
            unit=unit,
            formula=formula,
            use=use,
            requires=requires,
            limitations=limitations,
        )


group(
    "pace",
    "entry",
    ["completed clean laps <= as_of"],
    "Lap time is observed; causal tyre/fuel/weather attribution needs identifiable calibration.",
    [
        (
            "strategy_clean_laps",
            "laps",
            "Count accurate non-pit, non-deleted/generated laps with explicit clear track flag.",
            "Sample support for every pace decision.",
        ),
        (
            "strategy_recent_pace_s",
            "s/lap",
            "Median of last five eligible clean laps.",
            "Baseline race pace and pit projections.",
        ),
        (
            "strategy_pace_scatter_s",
            "s",
            "1.4826 * median absolute deviation of last ten clean lap times.",
            "Robust pace sensitivity and uncertainty.",
        ),
        (
            "strategy_pace_trend_s_per_lap",
            "s/lap",
            "Theil-Sen median pairwise slope over last ten clean lap times versus lap number.",
            "Detect pace trend without pretending it is pure tyre degradation.",
        ),
        (
            "strategy_last_lap_residual_s",
            "s",
            "Latest clean lap minus median of the preceding five clean laps.",
            "Flag unusual performance; check traffic/weather before attributing a mistake.",
        ),
        (
            "strategy_current_compound",
            "compound",
            "Compound from the latest already completed lap.",
            "Known tyre state; does not infer an unseen tyre change.",
        ),
        (
            "strategy_reported_tyre_age_laps",
            "laps",
            "Reported tyre life on latest completed lap.",
            "Initialize tyre curves without using future lap metadata.",
        ),
        (
            "strategy_common_lap_trend_s_per_lap",
            "s/lap",
            "OLS common race-lap coefficient with driver, compound and compound-specific tyre-age effects.",
            "Separate common fuel/evolution trend from wear when the design is identifiable.",
        ),
        (
            "strategy_compound_age_slopes",
            "s/lap",
            "OLS compound-specific age coefficients and 95% coefficient intervals from full-rank standardized design.",
            "Calibrate tyre scenarios; coefficient remains conditional and observational.",
        ),
        (
            "strategy_pace_design_condition",
            "ratio",
            "Largest divided by smallest singular value of standardized pace design.",
            "Reject collinear tyre/fuel models rather than manufacture precise coefficients.",
        ),
    ],
)
group(
    "rivals",
    "pair",
    ["matched lap/sector crossings", "fresh bounded positions"],
    "Positive time gap means focus is behind rival. Sector gaps are measured at equal timing lines, not simultaneously. Arc distance is geometry-estimated.",
    [
        (
            "rival_timing_gap_s",
            "s",
            "Latest t_focus(crossing)-t_rival(same crossing), both observed by cutoff.",
            "Anchor rival gap to an actual shared timing line.",
        ),
        (
            "rival_gap_observation_age_s",
            "s",
            "(as_of - max crossing timestamp)/1000.",
            "Expose staleness before pit-window decisions.",
        ),
        (
            "rival_mean_timing_gap_s",
            "s",
            "Mean of up to twenty latest matched timing-line gaps.",
            "Compare sustained separation rather than one sample.",
        ),
        (
            "rival_closing_rate_s_per_s",
            "s/s",
            "Negative Theil-Sen slope of matched clean end-lap gap versus observation clock.",
            "Project a gap trend; positive means focus is closing.",
        ),
        (
            "rival_pace_advantage_s_per_lap",
            "s/lap",
            "Median(rival clean lap - focus clean lap) on matching lap numbers, latest five.",
            "Estimate undercut pressure from comparable laps.",
        ),
        (
            "rival_projected_gap_s",
            "s",
            "Last gap - closing_rate*age, at most one pace lap old; reject pit/neutralized changes after anchor.",
            "Conditional gap at decision time with sensitivity bounds.",
        ),
        (
            "rival_catch_time_s",
            "s",
            "Projected positive gap / positive closing rate.",
            "Time to catch at unchanged pace; not an overtake guarantee.",
        ),
        (
            "rival_crossings_inside_2s_pct",
            "%",
            "100*count(0<matched_gap<=2)/number of matched crossings.",
            "Observed close-following exposure; not an inferred probability.",
        ),
        (
            "rival_mean_euclidean_distance_m",
            "m",
            "Mean simultaneous fresh interpolated XY separation on a shared one-second clock.",
            "Spatial context with adjacent-track/pit-lane caveats.",
        ),
        (
            "rival_min_euclidean_distance_m",
            "m",
            "Minimum simultaneous bounded XY separation.",
            "Locate proximity episodes without claiming contact.",
        ),
        (
            "rival_arc_ahead_m",
            "m",
            "(rival lap progress - focus lap progress)*reference length at same fresh timestamp.",
            "Along-track separation with lap count, avoiding Euclidean shortcuts.",
        ),
        (
            "rival_mean_arc_ahead_m",
            "m",
            "Mean plausible simultaneous signed race-distance difference.",
            "Time-series distance groundwork for traffic and blue-flag scenarios.",
        ),
        (
            "rival_pair_coverage_pct",
            "%",
            "100*valid simultaneous sampled instants/requested instants.",
            "Exclude stale tracking from race-state decisions.",
        ),
    ],
)
group(
    "pit",
    "entry",
    [
        "completed pit visits",
        "comparable clean in/out-lap neighbors",
        "known external stationary reports",
    ],
    "Pit-lane time, stationary service time and net race-time loss are different quantities. Retrospective estimates only use already completed laps.",
    [
        (
            "pit_latest_lane_duration_s",
            "s",
            "Latest observed paired pit-out minus pit-in.",
            "Baseline total visit and detect abnormal delay.",
        ),
        (
            "pit_field_lane_baseline_s",
            "s",
            "Median completed comparable same-phase lane visits, at least three.",
            "Reference for a rival's unusually long visit.",
        ),
        (
            "pit_latest_lane_excess_s",
            "s",
            "Latest lane duration minus comparable field median.",
            "Visit delay; cannot alone identify a slow wheel change.",
        ),
        (
            "pit_latest_stationary_duration_s",
            "s",
            "Latest source-reported stationary duration known by cutoff.",
            "Separate service from pit-lane travel when provider supports it.",
        ),
        (
            "pit_stationary_excess_s",
            "s",
            "Reported stationary duration minus median other comparable known service reports (n>=3).",
            "Identify service-time loss rather than confusing it with lane travel.",
        ),
        (
            "pit_net_loss_estimate_s",
            "s",
            "Median[(inlap+outlap) - (preceding clean lap + subsequent clean lap)], n>=3 green visits.",
            "Empirical net-loss candidate; neighbour tyre, traffic and warmup effects remain confounders.",
        ),
        (
            "pit_net_loss_scatter_s",
            "s",
            "1.4826*MAD of eligible paired-lap net-loss observations.",
            "Pit scenario sensitivity; not calibrated coverage.",
        ),
        (
            "pit_green_loss_input_s",
            "s",
            "Validated context green net loss, else supported empirical estimate.",
            "Cost to add to race-time strategy projections.",
        ),
        (
            "pit_sc_discount_s",
            "s",
            "Configured green net loss minus configured SC net loss.",
            "Compare actual/conditional neutralized stop cost.",
        ),
        (
            "pit_vsc_discount_s",
            "s",
            "Configured green net loss minus configured VSC net loss.",
            "VSC pit-cost scenario without a fixed universal discount.",
        ),
        (
            "pit_next_entry_distance_m",
            "m",
            "Forward reference-line distance from fresh car position to verified pit-entry progress.",
            "Know whether the pit entry is still ahead this lap.",
        ),
        (
            "pit_next_entry_eta_s",
            "s",
            "Historical reference-lap forward transit time scaled by current median pace; average-lap fallback is labelled.",
            "Propagate closing gaps to the next reachable pit decision boundary.",
        ),
    ],
)
group(
    "pit_windows",
    "pair",
    ["fresh rival gap", "net pit-loss model", "completed rival stop"],
    "Counterfactuals are conditional. Never subtract a rival's stop twice after the measured gap already contains it.",
    [
        (
            "pit_rejoin_gap_vs_rival_s",
            "s",
            "Projected focus gap + focus net pit loss.",
            "Positive means focus would rejoin behind this rival if rival stays out.",
        ),
        (
            "pit_free_stop_margin_s",
            "s",
            "-(projected focus gap + focus pit loss).",
            "Positive reserve before losing position to this rival.",
        ),
        (
            "pit_rival_normal_stop_counterfactual_gap_s",
            "s",
            "Actual current gap + rival's independently observed excess visit/service delay.",
            "Reconstruct a normal-stop counterfactual after actual gap has incorporated the stop.",
        ),
        (
            "pit_rival_delay_creates_window",
            "boolean",
            "Actual rejoin upper bound<0 AND normal-stop counterfactual rejoin lower bound>=0.",
            "Detect the specific opportunity created only by a rival's abnormal completed stop.",
        ),
        (
            "pit_undercut_break_even_laps",
            "laps",
            "First horizon where sum(old-rival projected lap - fresh-focus projected lap) exceeds positive current gap.",
            "Conditional tyre-only undercut threshold; overtaking and rival response are separate.",
        ),
    ],
)
group(
    "spatial_incident",
    "entry",
    ["fresh telemetry", "verified same-frame track/recovery geometry"],
    "Position is approximate. Spatial classes use an explicit error band; neither a racing-line deviation nor speed drop confirms a crash.",
    [
        (
            "incident_max_short_drop_kph",
            "km/h",
            "Maximum speed decline over <=2s of continuous plausible samples in latest 30s.",
            "Trigger incident inspection while retaining ordinary-braking explanations.",
        ),
        (
            "incident_current_stop_duration_s",
            "s",
            "Continuous latest observed speed<=5 km/h, no held gaps and fresh end observation.",
            "Distinguish momentary braking from a stopped obstruction.",
        ),
        (
            "incident_motion_state",
            "state",
            "Freshness, pit, slow movement, sustained stop and verified surface/recovery context.",
            "Explain candidate collision/retirement/recovery state without declaring mechanical cause.",
        ),
        (
            "incident_surface_clearance_m",
            "m",
            "Signed distance to union of supplied racing-surface polygons; positive inside.",
            "Distinguish confidently inside/outside from boundary-uncertain tracking.",
        ),
        (
            "incident_nearest_recovery_m",
            "m",
            "Minimum straight-line distance to supplied recovery access points.",
            "Input to calibrated incident cohorts; not actual accessible recovery path length.",
        ),
        (
            "incident_candidate_collision",
            "boolean",
            "Rapid drop>=100 km/h followed by >=4s fresh stop, outside known pits, with spatial context.",
            "Corroborated incident candidate for risk evaluation; never a confirmed crash.",
        ),
        (
            "incident_retirement_candidate",
            "boolean",
            "Fresh sustained stop>=30s outside pit with stopped-off-track/recovery spatial evidence.",
            "Retirement suspicion; loss of telemetry alone is not retirement.",
        ),
    ],
)
group(
    "weather_physics",
    "entry",
    [
        "fresh speed/heading",
        "fresh wind/pressure/temperature",
        "verified north alignment",
    ],
    "Weather station wind is not local car airflow. No car aero polar means no causal lap-time correction or tyre-blame attribution.",
    [
        (
            "weather_headwind_mps",
            "m/s",
            "Minus wind velocity dotted with car heading; weather direction is where wind comes FROM.",
            "Longitudinal aerodynamic exposure on this track segment.",
        ),
        (
            "weather_crosswind_right_mps",
            "m/s",
            "Wind velocity dotted with car's right unit vector.",
            "Direction-sensitive yaw/cornering exposure.",
        ),
        (
            "weather_relative_air_speed_mps",
            "m/s",
            "Magnitude(v_ground_vector - wind_vector).",
            "Correct velocity input to aerodynamic pressure.",
        ),
        (
            "weather_relative_air_yaw_deg",
            "deg",
            "atan2(relative-air-motion right component, forward component).",
            "Aero-yaw scenario input, not measured steering/yaw.",
        ),
        (
            "weather_moist_air_density_kg_m3",
            "kg/m3",
            "(pressure-vapour)/(287.05*T_K) + vapour/(461.495*T_K), vapour from humidity and saturation pressure.",
            "Density groundwork for pressure and force models.",
        ),
        (
            "weather_dynamic_pressure_pa",
            "Pa",
            "0.5*rho*relative_air_speed^2.",
            "Physical aero input; force additionally requires area and coefficients.",
        ),
        (
            "weather_dynamic_pressure_change_pct",
            "%",
            "100*(relative_air_speed^2/ground_speed^2 - 1).",
            "Relative pressure exposure, explicitly not a lap-time percentage.",
        ),
        (
            "vehicle_heading_xy_deg",
            "deg",
            "atan2(dy,dx) from fresh plausible movement.",
            "Track-local direction, independent of north calibration.",
        ),
        (
            "vehicle_turn_direction",
            "direction",
            "Sign of continuous wrapped change in path heading; positive=left in right-handed XY.",
            "Cornering context; not steering wheel angle.",
        ),
    ],
)
group(
    "safety_car",
    "session",
    [
        "incident state",
        "prior same-circuit labelled incident cohort",
        "fixed label horizon",
    ],
    "Empirical conditional probabilities, not exact predictions. Cohort labels must predate this race; no uncalibrated weighted score is called a probability.",
    [
        (
            "incident_sc_probability_pct",
            "%",
            "100*(n_any_SC+1)/(n+2), Beta(1,1) posterior mean; every cohort row must have known SC occurrence.",
            "Conditional P(SC within horizon | stopped/surface/recovery cohort).",
        ),
        (
            "incident_vsc_probability_pct",
            "%",
            "100*(n_any_VSC+1)/(n+2), Beta(1,1); VSC and SC may both occur within the horizon.",
            "Keep VSC distinct from full SC.",
        ),
        (
            "incident_red_probability_pct",
            "%",
            "100*(n_red+1)/(n+2), Beta(1,1) conditional estimate.",
            "Expose suspension risk separately; no generic pit saving assumed.",
        ),
        (
            "incident_no_neutralisation_probability_pct",
            "%",
            "100*(n_none+1)/(n+2), Beta(1,1) conditional estimate.",
            "Chance of no intervention; separate occurrence probabilities need not sum to 100%.",
        ),
        (
            "incident_response_distribution_pct",
            "%",
            "100*(n_class+1)/(n+4), Dirichlet(1,1,1,1) over mutually exclusive highest response: red > SC > VSC > none.",
            "A separate four-class outcome distribution that sums to 100%; SC then red belongs to red here, but counts as SC occurrence above.",
        ),
        (
            "incident_risk_cohort_n",
            "incidents",
            "Count unique earlier same-circuit incidents with identical state bins and label horizon.",
            "Expose evidence before displaying a percentage.",
        ),
        (
            "incident_risk_brier",
            "score",
            "Chronological expanding-window mean squared error of four-outcome Dirichlet predictions on held-out rows.",
            "Prequential calibration diagnostic; lower is better, not a guarantee.",
        ),
    ],
)
group(
    "planning",
    "entry",
    [
        "tyre curves/inventory",
        "pit-loss model",
        "remaining laps",
        "explicit rule profile",
    ],
    "Best means minimum modeled elapsed time among bounded legal configured plans. Race-wide traffic, passes, unknown tyres and future flags are not solved by this primitive.",
    [
        (
            "strategy_best_gain_vs_stay_out_s",
            "s",
            "Stay-out modeled time minus lowest feasible candidate modeled time.",
            "Quantify tyre/pit tradeoff under declared scenario assumptions.",
        ),
        (
            "strategy_first_stop_window_laps",
            "laps",
            "Minimum/maximum first-stop offsets among plans within max(1s,best sensitivity width) of best.",
            "Near-optimal pit window, not a falsely exact mandatory lap.",
        ),
        (
            "strategy_feasible_plan_count",
            "plans",
            "Number of evaluated plans satisfying configured inventory, tyre-age and race-rule constraints.",
            "Show search support and expose unavailable inputs.",
        ),
        (
            "strategy_rejoin_rank_estimate",
            "position",
            "1+number of selected field rivals with projected rejoin gap>0, only if all roster gaps fresh.",
            "Conditional rejoin order with complete field coverage.",
        ),
    ],
)


def catalog():
    return [definition.model_dump() for definition in DEFINITIONS.values()]
