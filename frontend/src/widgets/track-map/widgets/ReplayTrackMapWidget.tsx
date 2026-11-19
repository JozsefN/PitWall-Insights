import { useMemo } from "react";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import { illustratedRoadWidthLimitM } from "../utils/track-scale";
import { sessionCircuit } from "../../../features/circuits/circuit-catalog";
import { useWorkspaceReplayData } from "../../../features/sessions/workspace-replay-data";
import {
  getEntryAccent,
  getEntryDisplayName,
} from "../../../features/sessions/session-utils";
import { WidgetCard } from "../../shared/WidgetCard";
import {
  WidgetEmpty,
  WidgetError,
  WidgetLoading,
} from "../../shared/WidgetState";
import { CircuitMapLayers } from "../components/CircuitMapLayers";
import type { TrackMapWidgetOptions } from "../models";
import type { TrackMapEntryInput } from "../utils/track-map-data";
import { prepareReplayTrackMapData } from "../utils/track-map-data";

export function ReplayTrackMapWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const title =
    typeof options?.title === "string" ? options.title : "Replay Track Map";

  const workspace = useSessionWorkspace();
  const circuit = sessionCircuit(workspace.session);
  const widthLimitM = illustratedRoadWidthLimitM(circuit);
  const { position: positions, laps } = useWorkspaceReplayData();
  const entryIds = positions.entryIds;
  const entryIdsKey = entryIds.join(",");
  const prepareFrame = useMemo(() => {
    const selectedIds = new Set(entryIdsKey.split(","));
    const inputs: TrackMapEntryInput[] = workspace.entries
      .filter((entry) => selectedIds.has(entry.id))
      .map((entry, index) => ({
        entry,
        label: getEntryDisplayName(entry),
        color: getEntryAccent(entry, index),
        samples: positions.dataByEntryId[entry.id] ?? [],
        laps: laps.dataByEntryId[entry.id] ?? [],
      }));

    return prepareReplayTrackMapData(inputs, widthLimitM);
  }, [
    laps.dataByEntryId,
    positions.dataByEntryId,
    workspace.entries,
    entryIdsKey,
    widthLimitM,
  ]);
  const data = useMemo(
    () => prepareFrame(workspace.replay.minTimeMs),
    [prepareFrame, workspace.replay.minTimeMs],
  );

  if (workspace.entries.length === 0) {
    return (
      <WidgetCard title={title}>
        <WidgetEmpty message="No session entries were available for replay mode." />
      </WidgetCard>
    );
  }

  if (entryIds.length === 0) {
    return (
      <WidgetCard title={title}>
        <WidgetEmpty message="Choose drivers to load their track positions." />
      </WidgetCard>
    );
  }

  if (positions.isError || laps.isError) {
    return (
      <WidgetCard title={title}>
        <WidgetError message={positions.errorMessage} />
      </WidgetCard>
    );
  }

  if (!positions.ready) {
    return (
      <WidgetCard title={title}>
        <WidgetEmpty message={positions.waitMessage} />
      </WidgetCard>
    );
  }

  if (positions.isLoading || laps.isLoading) {
    return (
      <WidgetCard title={title}>
        <WidgetLoading />
      </WidgetCard>
    );
  }

  return (
    <WidgetCard title={title}>
      {data.outlinePoints.length === 0 && !data.drivers?.length ? (
        <WidgetEmpty message="Position telemetry was not available for replay mode." />
      ) : (
        <CircuitMapLayers
          key={workspace.selectedLayout?.id}
          data={data}
          circuit={circuit}
          mode="replay"
          replayFrame={prepareFrame}
          options={(options ?? {}) as TrackMapWidgetOptions}
        />
      )}
    </WidgetCard>
  );
}
