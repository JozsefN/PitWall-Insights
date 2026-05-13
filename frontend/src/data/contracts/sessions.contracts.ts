export type SessionImportProfile = "core" | "full";
export type SessionTelemetryStatus = "not_loaded" | "loaded" | "partial" | "unavailable";

export interface SessionCatalogItemDto {
  source: string;
  source_event_key: string;
  source_session_key: string;
  season_year: number;
  round_number: number | null;
  event_name: string;
  official_event_name: string | null;
  country: string | null;
  location: string | null;
  event_format: string | null;
  is_testing: boolean;
  session_name: string;
  session_type: string | null;
  scheduled_start_utc: string | null;
}

export interface SessionImportRequestDto {
  season_year: number;
  round_number: number;
  session_name: string;
  source_session_key?: string;
  import_profile?: SessionImportProfile;
  force_refresh?: boolean;
}

export interface SessionDto {
  id: string;
  source: string;
  source_session_key: string;
  season_year: number;
  round_number: number | null;
  event_name: string;
  official_event_name: string | null;
  country: string | null;
  location: string | null;
  session_name: string;
  session_type: string | null;
  import_profile: SessionImportProfile;
  telemetry_status: SessionTelemetryStatus;
  scheduled_start_utc: string | null;
  actual_start_utc: string | null;
  state: string;
  imported_at: string;
  last_accessed_at: string;
  expires_at: string;
  pinned_at: string | null;
  deleted_at: string | null;
  entry_count: number;
  tick_count: number;
  meeting_key?: string | null;
  session_key?: string | null;
  api_path?: string | null;
  f1_api_support?: boolean | null;
  weather_sample_count?: number;
  status_event_count?: number;
  track_status_event_count?: number;
  race_control_message_count?: number;
}

export interface SessionEntryDto {
  id: string;
  car_number: string;
  entry_type: string;
  status: string | null;
  grid_position: number | null;
  classified_position: number | null;
  driver_id: string;
  driver_number: string | null;
  driver_abbreviation: string | null;
  driver_name: string | null;
  team_id: string | null;
  team_name: string | null;
  team_color: string | null;
  result_position: number | null;
  laps_completed: number | null;
  points: number | null;
}

export interface EntryLapDto {
  id: string;
  lap_number: number;
  lap_position: number | null;
  stint_number: number | null;
  lap_time_ms: number | null;
  lap_start_time_ms: number | null;
  lap_end_time_ms: number | null;
  pit_out_time_ms: number | null;
  pit_in_time_ms: number | null;
  sector_1_time_ms: number | null;
  sector_2_time_ms: number | null;
  sector_3_time_ms: number | null;
  sector_1_session_time_ms: number | null;
  sector_2_session_time_ms: number | null;
  sector_3_session_time_ms: number | null;
  speed_i1_kph: number | null;
  speed_i2_kph: number | null;
  speed_fl_kph: number | null;
  speed_st_kph: number | null;
  compound: string | null;
  tyre_life: number | null;
  fresh_tyre: boolean | null;
  track_status: string | null;
  is_deleted: boolean;
  deleted_reason: string | null;
  is_generated: boolean;
  is_accurate: boolean;
}

export interface SessionTickDto {
  id: string;
  tick_no: number;
  session_time_ms: number;
  source_time_utc: string | null;
  source_kind: string;
}

export interface CarTelemetrySampleDto {
  id: string;
  tick_id: string;
  lap_id: string | null;
  stint_id: string | null;
  sample_seq: number;
  session_time_ms: number;
  source_time_utc: string | null;
  source: string | null;
  speed_kph: number | null;
  rpm: number | null;
  gear: number | null;
  throttle_pct: number | null;
  brake_on: boolean | null;
  drs_state: number | null;
}

export interface PositionSampleDto {
  id: string;
  tick_id: string;
  lap_id: string | null;
  stint_id: string | null;
  sample_seq: number;
  session_time_ms: number;
  source_time_utc: string | null;
  source: string | null;
  x: number | null;
  y: number | null;
  z: number | null;
  track_status: string | null;
}

export interface SessionTelemetryQuery {
  offset?: number;
  limit?: number;
  lap_number?: number;
  session_time_from_ms?: number;
  session_time_to_ms?: number;
}
