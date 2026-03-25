import { apiClient } from "./client";
import type { ApiHealthResponse, RootHealthResponse } from "../contracts/health.contracts";

export async function getRootHealth(): Promise<RootHealthResponse> {
  const { data } = await apiClient.get("/health");
  return data;
}

export async function getApiHealth(): Promise<ApiHealthResponse> {
  const { data } = await apiClient.get("/api/health");
  return data;
}