import { apiClient } from "./client";
import type {
  AuthSessionResponse,
  AuthResult,
  AuthTokenResponse,
  LoginRequest,
  SignUpRequest,
  VerificationRequired,
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

export async function signup(payload: SignUpRequest): Promise<VerificationRequired> {
  const { data } = await apiClient.post("/api/auth/signup", payload);
  return data;
}

export async function login(payload: LoginRequest): Promise<AuthResult> {
  const { data } = await apiClient.post("/api/auth/login", payload);
  return data;
}

export async function getAuthConfig() {
  return (await apiClient.get<{ email_verification_available: boolean }>("/api/auth/config")).data;
}

export async function verifyEmail(payload: { challenge_id: string; code: string }): Promise<AuthTokenResponse> {
  return (await apiClient.post<AuthTokenResponse>("/api/auth/verify-email", payload)).data;
}

export async function resendCode(challenge_id: string): Promise<VerificationRequired> {
  return (await apiClient.post<VerificationRequired>("/api/auth/resend-code", { challenge_id })).data;
}

export function logout(): void {
  localStorage.removeItem("auth_token");
}
