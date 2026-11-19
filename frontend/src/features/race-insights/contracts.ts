export const eventLabels = {
  braking_anomaly: "Possible braking / lockup anomaly",
  traction_disruption: "Possible traction disruption",
  possible_incident: "Possible incident",
  stopped_car: "Stopped car candidate",
  overtake: "On-track pass estimates",
  pit_stop: "Pit visits",
  pit_stop_delay: "Longer pit visits",
  yellow_flag: "Yellow flags",
  safety_car: "Safety car / VSC",
  red_flag: "Red flags",
  green_flag: "Green flags",
  track_status: "Race control / track status",
  track_limits: "Track limits reports",
  contact_report: "Race-control contact reports",
  damage_report: "Race-control damage reports",
  personal_best: "Personal best laps",
  session_best: "Session best laps",
  traffic_pressure: "Close following",
} as const;
export type EventKind = keyof typeof eventLabels;
export type EstimateValue = {
  value: number | string | null;
  unit: string;
  status: "available" | "insufficient_data" | "unavailable";
  method: "observed" | "derived" | "scenario" | "index";
  support: number;
  lower: number | null;
  upper: number | null;
  uncertainty: "sensitivity_range" | "sample_variation" | null;
  reason: string | null;
  unavailable_cause?: "missing_data" | "outside_window" | "not_applicable" | null;
};
export type RaceEvent = {
  id: string;
  kind: EventKind;
  time_ms: number;
  start_ms: number;
  entry_id: string | null;
  rival_entry_id: string | null;
  severity: "info" | "watch" | "warning";
  classification: "reported" | "observed" | "candidate";
  title: string;
  detail: string;
  support: number;
  evidence: Record<string, unknown>;
  alternatives: string[];
};
export type DriverEstimate = {
  entry_id: string;
  car_number: string;
  ahead_entry_id: string | null;
  metrics: Record<string, EstimateValue>;
  series: Array<Record<string, number | boolean | null>>;
  braking_zones: Array<{
    start_ms: number;
    duration_s: number;
    entry_speed_kph: number;
    exit_speed_kph: number;
    peak_deceleration_g: number;
    kinetic_loss_kjkg: number;
  }>;
  pace_laps: Array<{ lap: number; time_s: number; tyre_age: number | null; stint_number?: number | null; compound?: string | null }>;
};
export type RaceEstimates = {
  session_id: string;
  version: string;
  as_of_ms: number;
  start_ms: number;
  cache_hit: boolean;
  fingerprint: string;
  assumptions: Record<string, number | boolean | null>;
  drivers: DriverEstimate[];
  pairs: Array<{
    follower_id: string;
    ahead_id: string;
    gap_s: number | null;
    closing_rate: number | null;
    projected_gap_s: number | null;
    catch_time_s: number | null;
    attack_index: number | null;
    support: number;
    active_battle?: boolean;
    consistent_closing?: boolean;
    span_s?: number;
  }>;
  events: RaceEvent[];
  event_count: number;
  events_truncated: boolean;
  conditions: Record<string, string | number | boolean | null>;
  warnings: string[];
  interpretation: string;
};
