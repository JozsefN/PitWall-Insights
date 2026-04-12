import { useQueries } from "@tanstack/react-query";
import {
  listCarTelemetry,
  listEntryLaps,
  listPositionTelemetry,
} from "../../data/api/sessions.api";
import type { SessionTelemetryQuery } from "../../data/contracts/sessions.contracts";
import { useSessionWorkspace } from "./SessionWorkspaceContext";

export function useSelectedEntryLapsMap(enabled = true) {
  const workspace = useSessionWorkspace();
  return useEntryLapsMap(workspace.sessionId, workspace.selectedDriverIds, enabled);
}

export function useSelectedCarTelemetryMap(
  query?: SessionTelemetryQuery,
  enabled = true,
) {
  const workspace = useSessionWorkspace();
  return useCarTelemetryMap(workspace.sessionId, workspace.selectedDriverIds, query, enabled);
}

export function useSelectedPositionTelemetryMap(
  query?: SessionTelemetryQuery,
  enabled = true,
) {
  const workspace = useSessionWorkspace();
  return usePositionTelemetryMap(workspace.sessionId, workspace.selectedDriverIds, query, enabled);
}

export function useAllPositionTelemetryMap(
  query?: SessionTelemetryQuery,
  enabled = true,
) {
  const workspace = useSessionWorkspace();
  return usePositionTelemetryMap(
    workspace.sessionId,
    workspace.entries.map((entry) => entry.id),
    query,
    enabled,
  );
}

function useEntryLapsMap(sessionId: string, entryIds: string[], enabled: boolean) {
  const results = useQueries({
    queries: entryIds.map((entryId) => ({
      queryKey: ["sessions", sessionId, "entries", entryId, "laps"],
      queryFn: () => listEntryLaps(sessionId, entryId),
      enabled,
    })),
  });

  return {
    dataByEntryId: Object.fromEntries(
      entryIds.map((entryId, index) => [entryId, results[index]?.data ?? []]),
    ),
    isLoading: results.some((result) => result.isLoading),
    isError: results.some((result) => result.isError),
  };
}

function useCarTelemetryMap(
  sessionId: string,
  entryIds: string[],
  query: SessionTelemetryQuery | undefined,
  enabled: boolean,
) {
  const results = useQueries({
    queries: entryIds.map((entryId) => ({
      queryKey: ["sessions", sessionId, "entries", entryId, "telemetry", "car", query],
      queryFn: () => listCarTelemetry(sessionId, entryId, query),
      enabled,
    })),
  });

  return {
    dataByEntryId: Object.fromEntries(
      entryIds.map((entryId, index) => [entryId, results[index]?.data ?? []]),
    ),
    isLoading: results.some((result) => result.isLoading),
    isError: results.some((result) => result.isError),
  };
}

function usePositionTelemetryMap(
  sessionId: string,
  entryIds: string[],
  query: SessionTelemetryQuery | undefined,
  enabled: boolean,
) {
  const results = useQueries({
    queries: entryIds.map((entryId) => ({
      queryKey: ["sessions", sessionId, "entries", entryId, "telemetry", "position", query],
      queryFn: () => listPositionTelemetry(sessionId, entryId, query),
      enabled,
    })),
  });

  return {
    dataByEntryId: Object.fromEntries(
      entryIds.map((entryId, index) => [entryId, results[index]?.data ?? []]),
    ),
    isLoading: results.some((result) => result.isLoading),
    isError: results.some((result) => result.isError),
  };
}
