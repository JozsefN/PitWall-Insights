import { apiClient } from "./client";
import type { ModuleHealthResponse } from "../contracts/module-health.contracts";

export async function getStoryFeedHealth(): Promise<ModuleHealthResponse> {
  const { data } = await apiClient.get("/api/story-feed/health");
  return data;
}