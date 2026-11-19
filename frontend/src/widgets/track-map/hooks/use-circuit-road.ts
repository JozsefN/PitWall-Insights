import { skipToken, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { getCircuitRoad } from "../../../data/api/circuit-roads.api";
import { circuitRoadAssets } from "../../../features/circuits/circuit-catalog";
import type {
  CircuitDefinition,
  CircuitRoadAsset,
} from "../../../features/circuits/circuit-catalog";
import type { TrackMapPoint } from "../models";
import { registerCircuitRoad } from "../utils/circuit-registration";

export function useCircuitRoad(
  circuit: CircuitDefinition | undefined,
  outline: readonly TrackMapPoint[],
) {
  const assets = circuit ? circuitRoadAssets(circuit) : undefined;
  const hasReference = outline.length >= 32;
  const profile = useRegisteredRoad(assets?.profile, outline, hasReference);
  const centreline = useRegisteredRoad(
    assets?.centreline,
    outline,
    hasReference && (!assets?.profile || profile.isFetched) && !profile.value,
  );
  return profile.value ?? centreline.value;
}

function useRegisteredRoad(
  asset: CircuitRoadAsset | undefined,
  outline: readonly TrackMapPoint[],
  enabled: boolean,
) {
  const file = enabled ? asset?.file : undefined;
  const { data, isFetched } = useQuery({
    queryKey: ["circuit-roads", file],
    queryFn: file ? ({ signal }) => getCircuitRoad(file, signal) : skipToken,
    staleTime: Infinity,
    retry: false,
  });
  const road = useMemo(
    () => (data ? registerCircuitRoad(data, outline) : undefined),
    [data, outline],
  );
  return { isFetched, value: asset && road ? { asset, road } : undefined };
}
