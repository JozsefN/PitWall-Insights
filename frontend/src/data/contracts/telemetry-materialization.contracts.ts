export type TelemetryKind = "car" | "position";
export type TelemetryScope = "session" | "lap";
export type TelemetryMaterializationStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type TelemetryMaterializationStage =
  | "queued"
  | "loading_source"
  | "normalizing"
  | "persisting"
  | "completed"
  | "failed";

export interface TelemetryMaterializationRequestDto {
  session_id: string;
  entry_ids: string[];
  kinds: TelemetryKind[];
  scope: TelemetryScope;
  lap_number?: number;
  force_refresh?: boolean;
}

export interface TelemetrySegmentDto {
  id: string;
  session_id: string;
  session_entry_id: string;
  kind: TelemetryKind;
  scope: TelemetryScope;
  lap_number: number | null;
  status: TelemetryMaterializationStatus;
  row_count: number;
  source_version: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
}

export interface TelemetryMaterializationJobDto {
  id: string;
  session_id: string;
  entry_ids: string[];
  kinds: TelemetryKind[];
  scope: TelemetryScope;
  lap_number: number | null;
  status: TelemetryMaterializationStatus;
  progress_stage: TelemetryMaterializationStage;
  attempt_count: number;
  force_refresh: boolean;
  source_version: string | null;
  rows_written: number | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  heartbeat_at: string | null;
  finished_at: string | null;
  expires_at: string | null;
}

export interface TelemetryMaterializationEnsureResponseDto {
  ready: boolean;
  job_id: string | null;
  segments: TelemetrySegmentDto[];
}

export interface TelemetryMaterializationJobListResponseDto {
  jobs: TelemetryMaterializationJobDto[];
}
