import axios from "axios";
import { apiClient } from "./client";
import type { F1Connection, F1Credentials, Profile } from "../contracts/profile.contracts";

export async function getProfile(): Promise<Profile> {
  return (await apiClient.get<Profile>("/api/profile")).data;
}

export async function updateProfile(payload: Pick<Profile, "name" | "nickname" | "phone_number">): Promise<Profile> {
  return (await apiClient.patch<Profile>("/api/profile", payload)).data;
}

export async function connectF1(payload: F1Credentials): Promise<F1Connection> {
  return (await apiClient.post<F1Connection>("/api/profile/connections/f1", payload, { timeout: 100_000 })).data;
}

export async function disconnectF1(): Promise<F1Connection> {
  return (await apiClient.delete<F1Connection>("/api/profile/connections/f1")).data;
}

export async function verifyF1(): Promise<F1Connection> {
  return (await apiClient.post<F1Connection>("/api/profile/connections/f1/verify", null, { timeout: 100_000 })).data;
}

export function profileError(error: unknown): string {
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail?.message === "string") {
    return error.response.data.detail.message;
  }
  if (axios.isAxiosError(error) && typeof error.response?.data?.detail === "string") {
    return error.response.data.detail;
  }
  return "This change could not be completed. Please try again.";
}

export type DataCapability = { feature: string; supported: boolean; note: string };
export async function getDataCapabilities(): Promise<{ features: DataCapability[]; live_viewer_implemented: boolean; note: string }> {
  return (await apiClient.get("/api/ingestion/capabilities")).data;
}

export type BrowserAttempt = { id: string; url: string; expires_at: string };
export type BrowserStatus = { state: "waiting" | "verifying" | "ready" | "failed"; account_hint: string | null; error?: { message: string } };
export async function browserF1Available(): Promise<{ available: boolean }> {
  return (await apiClient.get("/api/profile/connections/f1/browser")).data;
}
export async function startBrowserF1(): Promise<BrowserAttempt> {
  return (await apiClient.post("/api/profile/connections/f1/browser", { personal_use_acknowledged: true })).data;
}
export async function browserF1Status(id: string): Promise<BrowserStatus> {
  return (await apiClient.get(`/api/profile/connections/f1/browser/${encodeURIComponent(id)}`)).data;
}
export async function confirmBrowserF1(id: string): Promise<F1Connection> {
  return (await apiClient.post(`/api/profile/connections/f1/browser/${encodeURIComponent(id)}/confirm`)).data;
}
export async function cancelBrowserF1(id: string): Promise<void> {
  await apiClient.delete(`/api/profile/connections/f1/browser/${encodeURIComponent(id)}`);
}
