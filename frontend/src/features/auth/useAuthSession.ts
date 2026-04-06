import { useQuery } from "@tanstack/react-query";
import { getAuthSession } from "../../data/api/auth.api";

export function useAuthSession() {
  return useQuery({
    queryKey: ["auth-session"],
    queryFn: getAuthSession,
    staleTime: 60_000,
  });
}