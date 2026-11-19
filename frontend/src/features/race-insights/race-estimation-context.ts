import { createContext, useContext } from "react";
import type { useRaceEstimates } from "./useRaceEstimates";

export const RaceEstimationContext = createContext<ReturnType<
  typeof useRaceEstimates
> | null>(null);
export function useRaceEstimationResource() {
  const resource = useContext(RaceEstimationContext);
  if (!resource)
    throw new Error("Race insight panels require RaceEstimationProvider");
  return resource;
}
