import { useState, type PropsWithChildren } from "react";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { apiClient } from "../../data/api/client";
import { useAuthSessionQuery } from "../../data/queries/auth.queries";
import { snapshotCutoff } from "../race-insights/presentation";
import {
  useReplayTime,
  useSessionWorkspace,
} from "../sessions/SessionWorkspaceContext";
import { retainSnapshot } from "../sessions/snapshot-refresh";
import type { RainScenario, ReplayStrategy } from "./replay-strategy.contracts";
import { StrategyReplayContext } from "./strategy-replay-context";

export function StrategyReplayProvider({
  enabled,
  children,
}: PropsWithChildren<{ enabled: boolean }>) {
  return enabled ? (
    <ActiveStrategyReplay>{children}</ActiveStrategyReplay>
  ) : (
    children
  );
}

function ActiveStrategyReplay({ children }: PropsWithChildren) {
  const workspace = useSessionWorkspace();
  const { data: auth } = useAuthSessionQuery();
  const [selection, setFocus] = useState("");
  const [scenario, setScenario] = useState<{
    session: string;
    value: RainScenario;
  } | null>(null);
  const time = useReplayTime("readout");
  const cutoff = snapshotCutoff(time);
  const { sessionId, entries, selectedDriverIds, replay, mode } = workspace;
  const weather =
    scenario?.session === sessionId &&
    scenario.value.issued_at_ms <= cutoff &&
    cutoff < scenario.value.ends_at_ms
      ? scenario.value
      : null;
  const focus = entries.some((entry) => entry.id === selection)
    ? selection
    : (selectedDriverIds[0] ?? entries[0]?.id ?? "");
  const query = useQuery({
    queryKey: ["replay-strategy", sessionId, cutoff, weather, auth?.user_id],
    queryFn: async ({ signal }) =>
      (
        await apiClient.post<ReplayStrategy>(
          `/api/strategy/sessions/${sessionId}/replay`,
          { as_of_ms: cutoff, rain_scenario: weather },
          { signal },
        )
      ).data,
    enabled: Boolean(auth?.user_id) && mode === "simulation" && replay.maxTimeMs > replay.minTimeMs,
    staleTime: 25_000,
    gcTime: 70_000,
    placeholderData: (previous, previousQuery) =>
      retainSnapshot(
        previous,
        previousQuery?.queryKey[4] === auth?.user_id && JSON.stringify(previous?.crossover?.forecast ?? null) ===
          JSON.stringify(weather),
        sessionId,
        cutoff,
      ),
    retry: (attempt, error) =>
      attempt < 2 &&
      axios.isAxiosError(error) &&
      [409, 429].includes(error.response?.status ?? 0),
    retryDelay: 1100,
  });
  return (
    <StrategyReplayContext.Provider
      value={{
        query,
        focus,
        setFocus,
        setRainScenario: (value) =>
          setScenario(value && { session: sessionId, value }),
      }}
    >
      {children}
    </StrategyReplayContext.Provider>
  );
}
