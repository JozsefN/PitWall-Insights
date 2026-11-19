import { hashKey, useQuery } from "@tanstack/react-query";
import axios from "axios";
import { apiClient } from "../../data/api/client";
import { useSessionReplayTimelineQuery } from "../../data/queries/sessions.queries";
import { useReplayTime, useSessionWorkspace } from "../sessions/SessionWorkspaceContext";
import { useTelemetryMaterializationReadiness } from "../sessions/session-data.hooks";
import { retainSnapshot } from "../sessions/snapshot-refresh";
import type { RaceEstimates } from "./contracts";
import { snapshotCutoff } from "./presentation";

// Identical keys across all panels share a single in-flight request and cache.
export function useRaceEstimates(enabled = true) {
  const workspace = useSessionWorkspace();
  const reviewTimeMs = useReplayTime("review");
  const timeline = useSessionReplayTimelineQuery(
    workspace.sessionId,
    enabled && workspace.mode === "lookback",
  );
  const ids = [...workspace.selectedDriverIds].sort();
  // The lookback insight panels use completed lap and timing records.
  const needsReplayTelemetry =
    enabled && workspace.mode === "simulation" && ids.length > 0;
  const car = useTelemetryMaterializationReadiness({
    entryIds: ids,
    kind: "car",
    scope: "session",
    enabled: needsReplayTelemetry,
  });
  const position = useTelemetryMaterializationReadiness({
    entryIds: ids,
    kind: "position",
    scope: "session",
    enabled: needsReplayTelemetry,
  });
  const currentTime =
    workspace.mode === "simulation"
      ? reviewTimeMs
      : (timeline.data?.at(-1)?.session_time_ms ?? 0);
  const cutoff = snapshotCutoff(currentTime);
  const scope = hashKey([workspace.mode, ids]);
  const query = useQuery({
    queryKey: [
      "race-estimates",
      workspace.sessionId,
      scope,
      cutoff,
      car.ready,
      position.ready,
    ],
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.post<RaceEstimates>(
        `/api/feature-metrics/sessions/${workspace.sessionId}/race-estimates`,
        {
          as_of_ms: cutoff,
          entry_ids: ids.length ? ids : undefined,
          lookback_ms: 300000,
          sample_interval_ms: 500,
          max_events: 500,
        },
        { signal },
      );
      return data;
    },
    enabled: enabled && (workspace.mode === "simulation" || timeline.isSuccess),
    placeholderData: (previous, previousQuery) =>
      retainSnapshot(
        previous,
        previousQuery?.queryKey[2] === scope,
        workspace.sessionId,
        cutoff,
      ),
    staleTime: 60000,
    gcTime: 120000,
    retry: (count, error) =>
      count < 2 &&
      axios.isAxiosError(error) &&
      [409, 429].includes(error.response?.status ?? 0),
    retryDelay: 2000,
  });
  const error = query.error;
  const detail =
    axios.isAxiosError(error) &&
    typeof error.response?.data?.detail === "string"
      ? error.response.data.detail
      : "The analysis could not be loaded. Retry when telemetry preparation finishes.";
  return {
    workspace,
    query,
    currentTime,
    cutoff,
    errorMessage: timeline.isError
      ? "The session timeline could not be loaded."
      : detail,
    preparing:
      needsReplayTelemetry &&
      ((!car.ready && !car.isError) || (!position.ready && !position.isError)),
    telemetryError: car.isError || position.isError,
    telemetryReadiness: { car, position },
  };
}
