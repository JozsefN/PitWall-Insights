import { apiClient } from "./client";
import type {
  TelemetryMaterializationEnsureResponseDto,
  TelemetryMaterializationJobDto,
  TelemetryMaterializationJobListResponseDto,
  TelemetryMaterializationRequestDto,
} from "../contracts/telemetry-materialization.contracts";

export async function ensureTelemetryMaterialization(
  payload: TelemetryMaterializationRequestDto,
): Promise<TelemetryMaterializationEnsureResponseDto> {
  const { data } = await apiClient.post("/api/telemetry/materialization/ensure", payload);
  return data;
}

export async function getTelemetryMaterializationJob(
  jobId: string,
): Promise<TelemetryMaterializationJobDto> {
  const { data } = await apiClient.get(`/api/telemetry/materialization/jobs/${jobId}`);
  return data;
}

export async function listTelemetryMaterializationJobs(
  limit = 25,
): Promise<TelemetryMaterializationJobListResponseDto> {
  const { data } = await apiClient.get("/api/telemetry/materialization/jobs", {
    params: { limit },
  });
  return data;
}
