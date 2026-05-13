import { useMutation, useQuery } from "@tanstack/react-query";
import {
  getSession,
  importSession,
  listCarTelemetry,
  listEntryLaps,
  listPositionTelemetry,
  listSessionCatalog,
  listSessionEntries,
  listSessionTicks,
  listSessions,
} from "../api/sessions.api";
import type {
  SessionImportRequestDto,
  SessionTelemetryQuery,
} from "../contracts/sessions.contracts";

export function useSessionsQuery() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions,
  });
}

export function useSessionCatalogQuery(season?: number) {
  return useQuery({
    queryKey: ["sessions", "catalog", season],
    queryFn: () => listSessionCatalog(season),
  });
}

export function useSessionQuery(
  sessionId?: string,
  enabled = true,
  refetchInterval: number | false = false,
) {
  return useQuery({
    queryKey: ["sessions", sessionId],
    queryFn: () => getSession(sessionId as string),
    enabled: Boolean(sessionId) && enabled,
    refetchInterval,
  });
}

export function useImportSessionMutation() {
  return useMutation({
    mutationFn: (payload: SessionImportRequestDto) => importSession(payload),
  });
}

export function useSessionEntriesQuery(sessionId?: string, enabled = true) {
  return useQuery({
    queryKey: ["sessions", sessionId, "entries"],
    queryFn: () => listSessionEntries(sessionId as string),
    enabled: Boolean(sessionId) && enabled,
  });
}

export function useEntryLapsQuery(
  sessionId?: string,
  entryId?: string,
  enabled = true,
) {
  return useQuery({
    queryKey: ["sessions", sessionId, "entries", entryId, "laps"],
    queryFn: () => listEntryLaps(sessionId as string, entryId as string),
    enabled: Boolean(sessionId && entryId) && enabled,
  });
}

export function useCarTelemetryQuery(
  sessionId?: string,
  entryId?: string,
  query?: SessionTelemetryQuery,
  enabled = true,
) {
  return useQuery({
    queryKey: ["sessions", sessionId, "entries", entryId, "telemetry", "car", query],
    queryFn: () => listCarTelemetry(sessionId as string, entryId as string, query),
    enabled: Boolean(sessionId && entryId) && enabled,
  });
}

export function usePositionTelemetryQuery(
  sessionId?: string,
  entryId?: string,
  query?: SessionTelemetryQuery,
  enabled = true,
) {
  return useQuery({
    queryKey: ["sessions", sessionId, "entries", entryId, "telemetry", "position", query],
    queryFn: () => listPositionTelemetry(sessionId as string, entryId as string, query),
    enabled: Boolean(sessionId && entryId) && enabled,
  });
}

export function useSessionTicksQuery(
  sessionId?: string,
  query?: {
    offset?: number;
    limit?: number;
  },
  enabled = true,
) {
  return useQuery({
    queryKey: ["sessions", sessionId, "ticks", query],
    queryFn: () => listSessionTicks(sessionId as string, query),
    enabled: Boolean(sessionId) && enabled,
  });
}
