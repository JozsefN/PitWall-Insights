import { apiClient } from "./client";
import type {
  FeatureMetricsHealthDetails,
  ModuleHealthResponse,
} from "../contracts/module-health.contracts";

export async function getFeatureMetricsHealth(): Promise<ModuleHealthResponse<FeatureMetricsHealthDetails>> {
  const { data } = await apiClient.get("/api/feature-metrics/health");
  return data;
}
