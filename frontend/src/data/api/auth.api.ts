import { apiClient } from "./client";
import type {
  AuthSessionResponse,
  AuthTokenResponse,
  LoginRequest,
  SignUpRequest,
} from "../contracts/auth.contracts";
import type { ModuleHealthResponse } from "../contracts/module-health.contracts";

export async function getAuthHealth(): Promise<ModuleHealthResponse> {
  const { data } = await apiClient.get("/api/auth/health");
  return data;
}

export async function getAuthSession(): Promise<AuthSessionResponse> {
  const { data } = await apiClient.get("/api/auth/session");
  return data;
}

export async function signup(payload: SignUpRequest): Promise<AuthTokenResponse> {
  const { data } = await apiClient.post("/api/auth/signup", payload);
  return data;
}

export async function login(payload: LoginRequest): Promise<AuthTokenResponse> {
  const { data } = await apiClient.post("/api/auth/login", payload);
  return data;
}

export function logout(): void {
  localStorage.removeItem("auth_token");
}