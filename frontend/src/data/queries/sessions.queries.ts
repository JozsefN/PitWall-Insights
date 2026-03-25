import { useQuery } from "@tanstack/react-query";
import { getSession, listSessions } from "../api/sessions.api";

export function useSessionsQuery() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions,
  });
}

export function useSessionQuery(sessionId?: string) {
  return useQuery({
    queryKey: ["sessions", sessionId],
    queryFn: () => getSession(sessionId as string),
    enabled: Boolean(sessionId),
  });
}