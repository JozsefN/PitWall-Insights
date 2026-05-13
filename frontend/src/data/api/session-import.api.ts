import { apiClient } from "./client";
import type { ImportJobDto, ImportJobListResponseDto } from "../contracts/session-import.contracts";
import type { SessionImportRequestDto } from "../contracts/sessions.contracts";

export async function createImportJob(payload: SessionImportRequestDto): Promise<ImportJobDto> {
  const { data } = await apiClient.post("/api/session-import/jobs", payload);
  return data;
}

export async function listImportJobs(limit = 25): Promise<ImportJobListResponseDto> {
  const { data } = await apiClient.get("/api/session-import/jobs", {
    params: { limit },
  });
  return data;
}

export async function getImportJob(jobId: string): Promise<ImportJobDto> {
  const { data } = await apiClient.get(`/api/session-import/jobs/${jobId}`);
  return data;
}
