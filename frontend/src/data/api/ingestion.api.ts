import { apiClient } from "./client";
import type {
  IngestionHealthDetails,
  ModuleHealthResponse,
} from "../contracts/module-health.contracts";

export async function getIngestionHealth(): Promise<ModuleHealthResponse<IngestionHealthDetails>> {
  const { data } = await apiClient.get("/api/ingestion/health");
  return data;
}
