import { useEffect, useMemo } from "react";
import { useSessionPitMapQuery } from "../../../data/queries/sessions.queries";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import { useTelemetryMaterializationReadiness } from "../../../features/sessions/session-data.hooks";
import { preparePitMap } from "../utils/pit-map";

export function useCircuitPitMap() {
  const { session, entries } = useSessionWorkspace();
  const query = useSessionPitMapQuery(
    session.id,
    (session.data_provider ?? session.source) === "openf1",
  );
  const { data, refetch } = query;
  const pits = useMemo(
    () => (data?.lane.length ? preparePitMap(data, entries) : undefined),
    [data, entries],
  );
  const referenceEntries = data?.reference_entry_ids ?? [];
  const preparation = useTelemetryMaterializationReadiness({
    entryIds: referenceEntries,
    kind: "position",
    scope: "session",
    enabled: !pits && referenceEntries.length > 0,
  });
  useEffect(() => {
    if (!pits && preparation.ready) void refetch({ cancelRefetch: false });
  }, [pits, preparation.ready, refetch]);
  return {
    pits,
    isLoading: query.isLoading,
    isError: query.isError,
    isPreparing: preparation.isPreparing,
    preparationFailed: preparation.isError,
  };
}
