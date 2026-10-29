import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { AUTH_EXPIRED_EVENT } from "../../features/auth/session-token";
import { getAuthHealth, getAuthSession } from "../api/auth.api";

export function useAuthHealthQuery() {
  return useQuery({
    queryKey: ["auth", "health"],
    queryFn: getAuthHealth,
  });
}

export function useAuthSessionQuery() {
  const client = useQueryClient();
  useEffect(() => {
    const expired = () =>
      client.setQueryData(["auth-session"], {
        authenticated: false,
        user_id: null,
        email: null,
      });
    window.addEventListener(AUTH_EXPIRED_EVENT, expired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expired);
  }, [client]);
  return useQuery({
    queryKey: ["auth-session"],
    staleTime: 60_000,
    queryFn: getAuthSession,
  });
}
