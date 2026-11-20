import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { AUTH_EXPIRED_EVENT } from "../../features/auth/session-token";
import { getAuthConfig, getAuthHealth, getAuthSession } from "../api/auth.api";

export const signedOutSession = {
  authenticated: false,
  user_id: null,
  email: null,
  role: null,
  email_verified: false,
};

export function useAuthConfigQuery() {
  return useQuery({ queryKey: ["auth-config"], queryFn: getAuthConfig, staleTime: 60_000 });
}

export function useAuthHealthQuery(enabled = true) {
  return useQuery({
    queryKey: ["auth", "health"],
    queryFn: getAuthHealth,
    enabled,
  });
}

export function useAuthSessionQuery() {
  const client = useQueryClient();
  useEffect(() => {
    const expired = () =>
      client.setQueryData(["auth-session"], signedOutSession);
    window.addEventListener(AUTH_EXPIRED_EVENT, expired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expired);
  }, [client]);
  return useQuery({
    queryKey: ["auth-session"],
    staleTime: 60_000,
    queryFn: getAuthSession,
  });
}
