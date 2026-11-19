import { createContext, useContext } from "react";
import { hashKey, useQuery } from "@tanstack/react-query";
import axios from "axios";
import { apiClient } from "../../data/api/client";
import { useReplayTime, useSessionWorkspace } from "../sessions/SessionWorkspaceContext";
import { retainSnapshot } from "../sessions/snapshot-refresh";
import { snapshotCutoff } from "../race-insights/presentation";
import type { LapChoice, RadioTimeline, ReviewData, ReviewGroup } from "./contracts";

type Parameters = {
  context_id?: string;
  horizon_laps?: number;
  fuel_burn_kg_per_lap?: number;
  fuel_time_s_per_kg?: number;
  repair_extra_s?: number;
  as_of_ms?: number;
};

export function useReviewQuery(
  groups: ReviewGroup[],
  laps: LapChoice[] = [],
  enabled = true,
  parameters?: Parameters,
  freshness?: boolean,
) {
  const workspace = useSessionWorkspace();
  const reviewTimeMs = useReplayTime("review");
  const cutoff =
    workspace.mode === "simulation"
      ? snapshotCutoff(reviewTimeMs)
      : parameters?.as_of_ms;
  const ids = [...workspace.selectedDriverIds].sort();
  const scope = hashKey([workspace.mode, groups, ids, laps, parameters]);
  return useQuery({
    queryKey: ["session-review", workspace.sessionId, scope, cutoff, freshness],
    queryFn: async ({ signal }) =>
      (
        await apiClient.post<ReviewData>(
          `/api/feature-metrics/sessions/${workspace.sessionId}/review`,
          {
            groups,
            entry_ids: ids.length ? ids : undefined,
            laps,
            ...parameters,
            as_of_ms: cutoff,
          },
          { signal },
        )
      ).data,
    enabled: enabled && groups.length > 0,
    placeholderData: (previous, previousQuery) =>
      retainSnapshot(
        previous,
        previousQuery?.queryKey[2] === scope,
        workspace.sessionId,
        cutoff,
      ),
    staleTime: 30000,
    gcTime: 60000,
    retry: (count, error) =>
      count < 3 && axios.isAxiosError(error) && error.response?.status === 429,
    retryDelay: (_, error) => {
      const seconds = axios.isAxiosError(error)
        ? Number(error.response?.headers["retry-after"])
        : NaN;
      return seconds > 0 ? Math.min(5000, seconds * 1000) : 750;
    },
  });
}

export const ReviewContext = createContext<ReturnType<
  typeof useReviewQuery
> | null>(null);
export function useSessionReview() {
  const value = useContext(ReviewContext);
  if (!value)
    throw new Error("Review panels require the session review provider");
  return value;
}

export function useRadioTimelineQuery() {
  const { sessionId, session } = useSessionWorkspace();
  return useQuery({
    queryKey: ["session-review", sessionId, "radio-timeline"],
    queryFn: async ({ signal }) => {
      const url = `/api/feature-metrics/sessions/${sessionId}/radio-timeline`;
      const { data } = await apiClient.get<RadioTimeline>(url, { signal });
      if (!data.available && session.source_session_key.startsWith("openf1:session:")) {
        return (await apiClient.post<RadioTimeline>(url, null, { signal })).data;
      }
      return data;
    },
    retry: false,
    staleTime: Infinity,
  });
}
