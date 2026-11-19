import { createContext, useContext } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import type { RainScenario, ReplayStrategy } from "./replay-strategy.contracts";

export const StrategyReplayContext = createContext<{
  query: UseQueryResult<ReplayStrategy>;
  focus: string;
  setFocus: (id: string) => void;
  setRainScenario: (value: RainScenario | null) => void;
} | null>(null);

export const replayStrategyPanelIds = [
  "strategy-call",
  "intervention-risk",
  "tyre-outlook",
  "rival-comparison",
  "rival-pit-scenarios",
  "tyre-crossover",
] as const;

export function useStrategyReplay() {
  const value = useContext(StrategyReplayContext);
  if (!value)
    throw new Error("Strategy panels require the replay strategy provider");
  return value;
}
