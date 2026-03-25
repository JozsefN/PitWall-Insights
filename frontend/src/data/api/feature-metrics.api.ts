import { apiClient } from "./client";
import type { ModuleHealthResponse } from "../contracts/module-health.contracts";

export async function getFeatureMetricsHealth(): Promise<ModuleHealthResponse> {
  const { data } = await apiClient.get("/api/feature-metrics/health");
  return data;
}