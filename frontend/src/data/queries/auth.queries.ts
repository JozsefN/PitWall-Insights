import { useQuery } from "@tanstack/react-query";
import { getAuthHealth, getAuthSession } from "../api/auth.api";

export function useAuthHealthQuery() {
  return useQuery({
    queryKey: ["auth", "health"],
    queryFn: getAuthHealth,
  });
}

export function useAuthSessionQuery() {
  return useQuery({
    queryKey: ["auth", "session"],
    queryFn: getAuthSession,
  });
}