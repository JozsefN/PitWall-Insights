import type { SessionImportProfile } from "./sessions.contracts";

export type ImportJobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export type ImportJobStage =
  | "queued"
  | "loading_source"
  | "normalizing"
  | "persisting"
  | "completed"
  | "failed";

export interface ImportJobDto {
  id: string;
  source: string;
  source_session_key: string | null;
  season_year: number;
  round_number: number;
  session_name: string;
  import_profile: SessionImportProfile;
  status: ImportJobStatus;
  progress_stage: ImportJobStage;
  attempt_count: number;
  force_refresh: boolean;
  created_by_user_id: string | null;
  session_id: string | null;
  source_version: string | null;
  rows_written: number | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  heartbeat_at: string | null;
  finished_at: string | null;
  expires_at: string;
}

export interface ImportJobListResponseDto {
  jobs: ImportJobDto[];
}
