export type Neutralisation = "sc" | "vsc" | "red" | "none";
export type TyreFamily = "SLICK" | "INTERMEDIATE" | "WET";
export type RainScenario = {
  issued_at_ms: number;
  starts_at_ms: number;
  ends_at_ms: number;
  probability_pct: number;
  intensity: "rain" | "heavy";
};
export type TyreComparison = {
  target: TyreFamily;
  sectors: Array<{
    sector: number;
    gain_s: number;
    spread_s: number;
    comparisons: number;
  }>;
  scouts: number;
  references: number;
  reference_compound: string | null;
  gain_s_lap: number | null;
  box_s: number | null;
  wait_s: number | null;
  earlier_switch_s: number | null;
  warmup_s: number | null;
  warmup_included: boolean;
  spread_s: number;
  historical_races: number;
  forecast_driven: boolean;
  supported: boolean;
};
export type CrossoverDecision = {
  entry_id: string;
  compound: string;
  action:
    | "observe"
    | "closed"
    | "outlap"
    | "box"
    | "forecast_box"
    | "wait"
    | "hold";
  target: TyreFamily | null;
  options: TyreComparison[];
  laps: number;
  arrival_s: number;
  pit_cost_s: number | null;
};

export type IncidentForecast = {
  horizon_s: number;
  episodes: number;
  races: number;
  reference_episodes?: number;
  scope: "circuit" | "pooled";
  outcomes_pct: Record<Neutralisation, number>;
  sc_interval_pct: [number, number];
};

export type StrategyWarning = {
  time_ms: number;
  kind: string;
  title: string;
  entry_ids: string[];
  detail: string;
  source: "race_control" | "telemetry_candidate";
  forecast: IncidentForecast | null;
};

export type StrategyPlan = {
  projected_time_s: number;
  green_time_s: number;
  neutralisation_saving_s: number;
  warmup_s?: number;
  exit_lap_beyond_observed_age?: boolean;
  pit_phase?: {
    basis: "historical_phase" | "current_phase_held";
    sc_pct: number;
    vsc_pct: number;
  };
  stops: Array<{ lap: number; compound: string }>;
};

export type StrategyCall = {
  action: "box" | "extend" | "finish";
  best: StrategyPlan;
  alternative: StrategyPlan | null;
  green_best: StrategyPlan;
  candidate_count: number;
  margin_s: number | null;
  margin_pct: number | null;
  decision_sensitive: boolean;
  sensitivity_s: number;
  pit_window: [number, number] | null;
  incident_changed_call: boolean;
  rival_context_id?: string;
};

export type RivalEvidence = {
  entry_id: string;
  gap_s: number | null;
  pre_pit_gap_s: number | null;
  pit_memory_seconds: number | null;
  championship_before: [number, number | null] | null;
  grid_gap: number | null;
  comparison: {
    lap_delta_s: number;
    scatter_s: number;
    laps: number;
    last_lap: number;
    sectors: Array<{ delta_s: number | null; laps: number }>;
  } | null;
  outlap?: {
    sector: number;
    lap: number;
    at_ms: number;
    compound: string;
    split_s: number;
    peers: number;
    loss_s: number | null;
    typical_warmup_s?: number | null;
    remaining_loss_s: number | null;
    scatter_s: number | null;
    rejoin_margin_s?: number;
    projected_rejoin_margin_s?: number;
    uncertain_flip?: boolean;
  };
};

export type RivalScenario = {
  assumption: "holds" | "boxes" | "finishes";
  rival_first_stop: StrategyPlan["stops"][number] | null;
  preferred_action: StrategyCall["action"];
  choices: Array<{
    action: StrategyCall["action"];
    first_stop: StrategyPlan["stops"][number] | null;
    finish_margin_s: number;
    crossover_lap: number | null;
    positions_lost: number | null;
    post_pit_pace_advantage_s: number | null;
    traffic_loss_s: number;
    cost_vs_best_s: number;
  }>;
};

export type DriverStrategy = {
  entry_id: string;
  completed_laps: number;
  compound: string | null;
  tyre_age: number | null;
  observed_age_limit: number | null;
  supported_laps_left: number | null;
  gap_to_leader_s: number | null;
  gap_ahead_s: number | null;
  stint: {
    pace_s?: number | null;
    clean_laps?: number;
    current_change_pct?: number | null;
    persistent_loss_s_lap?: number;
    loss_after_warning?: string | null;
    braking_evidence_ms?: number;
    laps_to_one_percent_slower?: number;
  };
  call: StrategyCall | null;
  status: string | null;
  rivals?: RivalEvidence[];
  matchups?: Array<{
    rival_entry_id: string;
    scenarios: RivalScenario[];
    slow_stop_window?: {
      basis: "stationary" | "lane";
      excess_s: number;
      margin_s: number;
      normal_margin_s: number;
      samples: number;
    } | null;
  }>;
  following?: {
    effect_s_lap: number;
    close_laps: number;
    clear_laps: number;
    scatter_s: number;
  } | null;
  rejoin_if_pit?: {
    position: number;
    timed_drivers: number;
    gap_to_leader_s: number;
  } | null;
};

export type CompoundProfile = {
  runs: number;
  practice_runs: number;
  previous_race_runs: number;
  current_race_runs: number;
  observed_age: number;
  drift_s_lap: number;
  slope_scatter: number;
  pace_scatter_s: number;
  practice_change_pct: number | null;
};

export type ReplayStrategy = {
  version: string;
  session_id: string;
  as_of_ms: number;
  crossover?: {
    active: boolean;
    rain_reported: boolean | null;
    field: Record<TyreFamily, number>;
    forecast: RainScenario | null;
    grip: Array<{ sector: number; slowdown_s: number; drivers: number }>;
    decisions: Record<string, CrossoverDecision>;
  };
  total_laps: number | null;
  leader_completed_laps: number;
  status: string | null;
  pit: {
    median_s: number | null;
    robust_scatter_s: number | null;
    sample_count: number;
    green_basis?:
      | "timing_sectors"
      | "same_circuit_timing_archive"
      | "whole_laps";
    discount_s: { sc: number | null; vsc: number | null };
    discount_basis?: Partial<
      Record<
        "sc" | "vsc",
        {
          scope:
            | "timing_sectors"
            | "same_circuit_sector_archive"
            | "circuit_adjusted_sector_archive"
            | "pooled_sector_archive"
            | "local_laps"
            | "same_circuit_archive"
            | "pooled_archive";
          samples: number;
          pace_ratio?: number;
        }
      >
    >;
  };
  compound_profiles: Record<string, CompoundProfile>;
  warnings: StrategyWarning[];
  incident: {
    forecast: IncidentForecast | null;
    episode_start_ms: number | null;
    phase: string | null;
    pit_entry_closed?: boolean;
  };
  drivers: DriverStrategy[];
};
