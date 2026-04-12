import { apiClient } from "./client";
import type {
  ModuleHealthResponse,
  StoryFeedHealthDetails,
} from "../contracts/module-health.contracts";

export async function getStoryFeedHealth(): Promise<ModuleHealthResponse<StoryFeedHealthDetails>> {
  const { data } = await apiClient.get("/api/story-feed/health");
  return data;
}
