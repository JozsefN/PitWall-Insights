export type ReviewGroup =
  | "drivers"
  | "segments"
  | "radio"
  | "racecraft"
  | "pace"
  | "pit"
  | "incidents"
  | "weather"
  | "flags"
  | "surface";
export type LapChoice = { entry_id: string; lap_number: number };
export type DriverCard = {
  entry_id: string;
  car_number: string;
  name: string | null;
  abbreviation: string | null;
  team: string | null;
  headshot_url: string | null;
  best_clean_lap_s: number | null;
  best_clean_lap_number: number | null;
  recent_clean_lap_numbers: number[];
  qualifying: Array<{
    phase: number;
    lap_time_s: number;
    lap_number: number | null;
    gap_to_phase_best_s: number;
    provider_colours: string[][];
  }>;
};
export type Segment = {
  segment: number;
  time_s: number;
  delta_to_best_s: number | null;
  delta_to_prior_median_s: number | null;
  min_speed_kph: number | null;
  mean_throttle_pct: number | null;
  brake_sample_pct: number | null;
  colour: string;
};
export type Benchmark = {
  median_s: number | null;
  robust_scatter_s: number | null;
  sample_count: number;
  session_ids: string[];
};
export type RadioClip = {
  entry_id: string;
  time_ms: number;
  known_at_ms?: number;
  recording_url: string;
};
export type RadioTimeline = {
  available: boolean;
  clips: Array<RadioClip & {
    feed_time_ms: number;
    timing_basis: "estimated_recording" | "source_feed";
  }>;
};
export type ReviewData = {
  session_id: string;
  as_of_ms: number;
  qualifying: boolean;
  groups: {
    drivers?: DriverCard[];
    radio?: {
      available: boolean;
      clips: RadioClip[];
    };
    segments?: {
      laps: Array<LapChoice & { lap_time_s: number; segments: Segment[] }>;
      method: string;
      supported: number;
    };
    racecraft?: {
      close_following_threshold_s?: number;
      battles: Array<{
        follower_id: string;
        ahead_id: string;
        active_battle: boolean;
        consistent_closing: boolean;
        gap_s: number;
        span_s: number;
        sample_count: number;
        pace_advantage_s_per_lap?: number;
        follower_compound?: string;
        ahead_compound?: string;
      }>;
      passes: Array<{
        id: string;
        entry_id: string;
        rival_entry_id: string;
        time_ms: number;
      }>;
    };
    pace?: {
      drivers: Array<{
        entry_id: string;
        samples: number;
        median_pace_s: number;
        faster_observed_pace_s: number;
        traffic_pace_s: number | null;
        clear_pace_s: number | null;
        observed_trend_s_per_lap: number | null;
        fuel_scenario_trend_s_per_lap: number | null;
      }>;
      practice_profiles: Array<{
        compound: string;
        runs: number;
        longest_observed_clean_run_laps: number;
        median_observed_trend_s_per_lap: number;
      }>;
      track_evolution: {
        matched_drivers: number;
        pace_change_s_per_min: number | null;
      };
      horizon_laps: number;
      fuel_scenario_gain_s_per_lap: number | null;
      field_projection: Array<{
        entry_id: string;
        projected_gap_s?: number;
        order_among_projected_entries?: number;
        laps_down_reported: number;
      }>;
      lapped_traffic_scenarios: Array<{
        entry_id: string;
        lapped_entry_id: string;
        catch_after_laps: number;
        progress_pct: number;
        reference_shape: string;
        delay_sensitivity_s: [number, number];
      }>;
    };
    pit?: {
      net_green_pit_loss: Benchmark;
      pit_lane_duration: Benchmark;
      stationary_service_duration: Benchmark;
      exit_scenarios: Array<{
        entry_id: string;
        exit_order_among_timed_entries: number;
        timed_entries: number;
        projected_gap_to_current_leader_s: number;
        total_repair_stop_loss_s: number | null;
      }>;
      rival_windows: Array<{
        entry_id: string;
        rival_entry_id: string;
        rival_stop_excess_s: number;
        exit_margin_s: number;
        normal_rival_stop_margin_s?: number;
        position_flip_scenario: boolean;
      }>;
    };
    incidents?: {
      reports: Array<{
        kind: string;
        entry_ids: string[];
        time_ms: number;
        message: string;
        lap_number: number | null;
      }>;
      damage_estimation: string;
      report_counts: Array<{
        entry_id: string;
        report_kind: string;
        count: number;
      }>;
      post_report_pace: Array<{
        entry_id: string;
        pace_change_s: number;
        samples_before: number;
        samples_after: number;
      }>;
    };
    weather?: {
      current: WeatherPoint | null;
      timeline: WeatherPoint[];
      reason: string;
    };
    flags?: {
      track_flag: string | null;
      sectors: Array<{ number: number; flag: string }>;
      unlocated_caution: boolean;
    };
    surface?: {
      availability: string;
      reason: string;
      source_uri?: string;
      source_license?: string | null;
      circuit_length_m?: number | null;
      position_error_m?: number;
      recovery_points_m?: [number, number][];
      zones: Array<{
        zone_id: string;
        kind: string;
        sector_number?: number | null;
        polygon_m: [number, number][];
      }>;
      cars: Array<{
        entry_id: string;
        x_m: number;
        y_m: number;
        contained_in: string[];
        beyond_mapped_track_candidate: boolean;
        terrain?: string | null;
        nearest_recovery_m?: number | null;
      }>;
    };
  };
};
export type WeatherPoint = {
  time_ms: number;
  wind_speed_ms: number | null;
  wind_direction_deg: number | null;
  rain_reported: boolean | null;
  track_temperature_c: number | null;
  air_temperature_c: number | null;
};
