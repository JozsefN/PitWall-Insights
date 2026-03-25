import { apiClient } from "./client";
import type { AuthSessionResponse } from "../contracts/auth.contracts";
import type { ModuleHealthResponse } from "../contracts/module-health.contracts";

export async function getAuthHealth(): Promise<ModuleHealthResponse> {
  const { data } = await apiClient.get("/api/auth/health");
  return data;
}

export async function getAuthSession(): Promise<AuthSessionResponse> {
  const { data } = await apiClient.get("/api/auth/session");
  return data;
}