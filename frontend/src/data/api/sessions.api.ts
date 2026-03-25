import { apiClient } from "./client";
import type { SessionDto } from "../contracts/sessions.contracts"

export async function listSessions(): Promise<SessionDto[]> {
  const { data } = await apiClient.get("/api/sessions");
  return data;
}

export async function getSession(sessionId: string): Promise<SessionDto> {
  const { data } = await apiClient.get(`/api/sessions/${sessionId}`);
  return data;
}