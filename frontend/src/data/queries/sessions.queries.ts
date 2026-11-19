import { useMutation, useQuery } from "@tanstack/react-query";
import {
  getSession,
  getReplayTimeline,
  getSessionPitMap,
  getSessionTimingTower,
  importSession,
  listCarTelemetry,
  listEntryLaps,
  listPositionTelemetry,
  listSessionCatalog,
  listSessionEntries,
  listSessionTrackStatusEvents,
  listSessionTicks,
  listSessions,
} from "../api/sessions.api";
import type {
  SessionImportRequestDto,
  SessionTelemetryQuery,
} from "../contracts/sessions.contracts";
import { buildReplayClock } from "../../features/sessions/replay-timeline";

export function useSessionTimingTowerQuery(sessionId: string) {
  return useQuery({
    queryKey: ["sessions", sessionId, "timing-tower"],
    queryFn: ({ signal }) => getSessionTimingTower(sessionId, signal),
    staleTime: Infinity,
    retry: false,
  });
}

export function useSessionReplayTimelineQuery(
  sessionId?: string,
  enabled = true,
) {
  return useQuery({
    ...sessionTimeBoundsOptions(sessionId, enabled),
    select: (data) => buildReplayClock(data.start_time_ms, data.end_time_ms),
  });
}

export function useSessionTimeBoundsQuery(sessionId?: string, enabled = true) {
  return useQuery(sessionTimeBoundsOptions(sessionId, enabled));
}

function sessionTimeBoundsOptions(
  sessionId: string | undefined,
  enabled: boolean,
) {
  return {
    queryKey: ["sessions", sessionId, "replay-timeline"],
    queryFn: () => getReplayTimeline(sessionId as string),
    enabled: Boolean(sessionId) && enabled,
    staleTime: Infinity,
  };
}

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

export function useSessionPitMapQuery(sessionId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["sessions", sessionId, "pit-map"],
    queryFn: ({ signal }) => getSessionPitMap(sessionId, signal),
    enabled,
    staleTime: 30_000,
    retry: false,
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
    queryKey: [
      "sessions",
      sessionId,
      "entries",
      entryId,
      "telemetry",
      "car",
      query,
    ],
    queryFn: () =>
      listCarTelemetry(sessionId as string, entryId as string, query),
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
    queryKey: [
      "sessions",
      sessionId,
      "entries",
      entryId,
      "telemetry",
      "position",
      query,
    ],
    queryFn: () =>
      listPositionTelemetry(sessionId as string, entryId as string, query),
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

export function useSessionTrackStatusEventsQuery(
  sessionId?: string,
  query?: {
    offset?: number;
    limit?: number;
  },
  enabled = true,
) {
  return useQuery({
    queryKey: ["sessions", sessionId, "track-status-events", query],
    queryFn: () => listSessionTrackStatusEvents(sessionId as string, query),
    enabled: Boolean(sessionId) && enabled,
  });
}
