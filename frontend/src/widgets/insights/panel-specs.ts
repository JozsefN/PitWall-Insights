import type { TelemetryKind } from "../../data/contracts/telemetry-materialization.contracts";

export const insightPanels = {
  "race-notifications": {
    title: "Race notifications",
    description:
      "Race control, reported events and optional detection candidates.",
    metrics: [],
  },
  "driver-overview": {
    title: "Driver overview",
    description: "Current running, recent pace and the next car ahead.",
    metrics: [
      "current_speed_kph",
      "ahead_gap_s",
      "recent_pace_s",
      "tyre_age_laps",
      "last_lap_delta_s",
      "current_throttle_pct",
    ],
  },
  "battle-radar": {
    title: "Battle radar",
    description: "Running-order neighbours from fresh timing reports.",
    metrics: [
      "nearby_car_count",
      "ahead_gap_s",
      "gap_closing_rate",
      "defence_pressure_index",
    ],
  },
  "wake-exposure": {
    title: "Wake & traffic",
    description: "Following exposure and aerodynamic sensitivity scenarios.",
    metrics: [
      "ahead_distance_scenario_m",
      "close_following_s",
      "traffic_time_pct",
      "wake_loss_scenario_pct",
      "corner_speed_loss_scenario_pct",
      "wake_extra_work_index",
    ],
  },
  "tyre-workload": {
    title: "Tyre workload",
    description:
      "Relative workload and cooling scenarios, without temperature or wear claims.",
    metrics: [
      "tyre_age_laps",
      "tyre_thermal_load_index",
      "corner_load_index",
      "traction_load_index",
      "wear_pressure_index",
      "wake_extra_work_index",
    ],
  },
  "braking-analysis": {
    title: "Braking analysis",
    description:
      "Brake episodes, deceleration and energy dissipated per unit mass.",
    metrics: [
      "braking_zone_count",
      "peak_deceleration_g",
      "braking_kinetic_loss_kjkg",
      "brake_point_shift_m",
      "braking_anomaly_count",
      "brake_time_pct",
    ],
  },
  "pace-context": {
    title: "Pace context",
    description: "Comparable completed laps and traffic association.",
    metrics: [
      "recent_pace_s",
      "clean_air_reference_s",
      "last_lap_delta_s",
      "traffic_correlated_loss_s",
      "pace_consistency_pct",
      "pace_sample_laps",
    ],
  },
  "closing-gaps": {
    title: "Gap evolution",
    description:
      "Measured headways, closing trends and a 10-second extrapolation.",
    metrics: [
      "ahead_gap_s",
      "gap_closing_rate",
      "projected_gap_s",
      "catch_time_s",
      "mean_ahead_gap_s",
      "mean_headway_distance_m",
    ],
  },
  "overtake-opportunities": {
    title: "Attack & defence",
    description: "Relative opportunity indices with DRS and tow context.",
    metrics: [
      "attack_opportunity_index",
      "defence_pressure_index",
      "drs_active_pct",
      "tow_exposure_s",
      "tow_drag_relief_scenario_pct",
      "gap_closing_rate",
    ],
  },
  "pit-scenarios": {
    title: "Pit scenarios",
    description:
      "Assumed net pit loss, adjacent-car margins and reported visit durations.",
    metrics: [
      "pit_loss_scenario_s",
      "pit_exit_margin_scenario_s",
      "pit_lane_duration_median_s",
      "latest_stop_delta_s",
      "one_lap_undercut_scenario_s",
      "laps_to_pace_limit_scenario",
    ],
  },
  "incident-watch": {
    title: "Incident watch",
    description:
      "Stopped-car and abrupt-slowdown candidates alongside official reports.",
    metrics: [
      "current_stopped_s",
      "abrupt_slowdown_count",
      "incident_concern_index",
      "latest_sample_age_s",
    ],
  },
  "track-conditions": {
    title: "Track & weather",
    description:
      "Reported track state and weather with explicit wind limitations.",
    metrics: [
      "air_temperature_c",
      "track_temperature_c",
      "air_density_kgm3",
      "wind_speed_ms",
      "headwind_ms",
      "crosswind_ms",
      "relative_air_speed_kph",
      "dynamic_pressure_pa",
      "wind_pressure_shift_pct",
      "relative_air_speed_low_kph",
      "relative_air_speed_high_kph",
    ],
  },
  "stint-performance": {
    title: "Stint performance",
    description: "Tyre age, completed-lap trend and workload context.",
    metrics: [
      "tyre_age_laps",
      "stint_pace_slope",
      "pace_consistency_pct",
      "recent_pace_s",
      "laps_to_pace_limit_scenario",
      "wear_pressure_index",
    ],
  },
  "driver-comparison": {
    title: "Driver comparison",
    description:
      "Compare two selected drivers using the same cutoff and assumptions.",
    metrics: [
      "recent_pace_s",
      "last_lap_delta_s",
      "tyre_age_laps",
      "stint_pace_slope",
      "traffic_time_pct",
      "peak_deceleration_g",
      "tyre_thermal_load_index",
      "telemetry_coverage_pct",
    ],
  },
  "model-quality": {
    title: "Model evidence",
    description: "Coverage, freshness, modelling assumptions and limitations.",
    metrics: [
      "telemetry_coverage_pct",
      "gap_coverage_pct",
      "latest_sample_age_s",
      "observed_window_s",
      "neutralised_time_pct",
    ],
  },
} as const;
export type InsightPanelId = keyof typeof insightPanels;

export const insightPanelGuide: Record<InsightPanelId, string> = {
  "race-notifications":
    "Follow recent flags, reports and detected events as you replay. Open a message to see its evidence.",
  "driver-overview":
    "Select a driver to check their speed, tyres and gap at the replay clock. Use the map's Focus control to follow the same car.",
  "battle-radar":
    "Use during green-flag running to compare neighbours. A sustained closing trend matters more than one gap sample.",
  "wake-exposure":
    "Seek to a green-flag lap where the driver is following closely. Compare the speed trace and timed gap before interpreting the wake scenario.",
  "tyre-workload":
    "Compare similar runs to see where tyre workload rises. Use the stint panel to check whether completed-lap pace fell as well.",
  "braking-analysis":
    "Seek to a heavy braking zone. Check the speed trace before treating an anomaly as a possible lock-up.",
  "pace-context":
    "Use after several clean laps on comparable tyres. Check traffic, rain and neutralisations before interpreting pace loss.",
  "closing-gaps":
    "Follow the same pair over several samples. A positive closing rate means the follower is gaining.",
  "overtake-opportunities":
    "Use with a fresh gap during green-flag running. Relative attack and defence indices help prioritize which battles to watch.",
  "pit-scenarios":
    "Use before a planned stop. Compare pit loss and rival margins with Pit loss & rejoin when enough comparable stops are available.",
  "incident-watch":
    "Seek to an abrupt slowdown or stop and check the map and race-control reports for corroboration.",
  "track-conditions":
    "Check track temperature and rain when comparing laps. Use the map's Wind & rain layer for the reported bearing.",
  "stint-performance":
    "Use after several comparable laps on the same set. A slower trend can reflect traffic or conditions as well as the tyres.",
  "driver-comparison":
    "Select at least two drivers and compare them at the same replay time or completed-session cutoff.",
  "model-quality":
    "Check timing and telemetry coverage before using an estimate in a strategy decision.",
};

// Optional evidence enriches other panels without delaying playback.
export const insightReplayTelemetry: Partial<
  Record<InsightPanelId, TelemetryKind[]>
> = {
  "driver-overview": ["car"],
  "wake-exposure": ["car", "position"],
  "tyre-workload": ["car", "position"],
  "braking-analysis": ["car"],
  "overtake-opportunities": ["car"],
  "incident-watch": ["car", "position"],
};
