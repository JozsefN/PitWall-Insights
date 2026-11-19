import type { ReactNode } from "react";
import { useRaceEstimates } from "./useRaceEstimates";
import { RaceEstimationContext } from "./race-estimation-context";

export function RaceEstimationProvider({
  children,
  enabled,
}: {
  children: ReactNode;
  enabled: boolean;
}) {
  const resource = useRaceEstimates(enabled);
  return (
    <RaceEstimationContext.Provider value={resource}>
      {children}
    </RaceEstimationContext.Provider>
  );
}
