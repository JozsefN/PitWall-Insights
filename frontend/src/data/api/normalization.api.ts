import { apiClient } from "./client";
import type {
  ModuleHealthResponse,
  NormalizationHealthDetails,
} from "../contracts/module-health.contracts";

export async function getNormalizationHealth(): Promise<ModuleHealthResponse<NormalizationHealthDetails>> {
  const { data } = await apiClient.get("/api/normalization/health");
  return data;
}
