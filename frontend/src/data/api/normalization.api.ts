import { apiClient } from "./client";
import type { ModuleHealthResponse } from "../contracts/module-health.contracts";

export async function getNormalizationHealth(): Promise<ModuleHealthResponse> {
  const { data } = await apiClient.get("/api/normalization/health");
  return data;
}