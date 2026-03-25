import { apiClient } from "./client";
import type { ModuleHealthResponse } from "../contracts/module-health.contracts";

export async function getIngestionHealth(): Promise<ModuleHealthResponse> {
  const { data } = await apiClient.get("/api/ingestion/health");
  return data;
}