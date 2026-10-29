import { useMemo } from "react";
import {
  useWorkspaceEntryLapsResource,
  useWorkspacePositionTelemetryResource,
} from "../../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import { replaySampleInterval } from "../../../features/sessions/replay-timeline";
import {
  formatSessionClock,
  getEntryAccent,
  getEntryDisplayName,
} from "../../../features/sessions/session-utils";
import { useSessionCircuitCornersQuery } from "../../../data/queries/sessions.queries";
import { WidgetCard } from "../../shared/WidgetCard";
import {
  WidgetEmpty,
  WidgetError,
  WidgetLoading,
} from "../../shared/WidgetState";
import { TrackMapViewer } from "../components/TrackMapViewer";
import { buildTrackMapTurnMarkers } from "../utils/circuit-corners";
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
  const entryIds =
    workspace.selectedDriverIds.length > 0
      ? workspace.selectedDriverIds
      : workspace.entries.map((entry) => entry.id);
  const positions = useWorkspacePositionTelemetryResource({
    entryIds,
    scope: "session",
    limit: 20000,
    sampleIntervalMs: replaySampleInterval(
      workspace.replay.minTimeMs,
      workspace.replay.maxTimeMs,
    ),
    sessionTimeFromMs: workspace.replay.minTimeMs,
    sessionTimeToMs: workspace.replay.maxTimeMs || undefined,
    enabled: entryIds.length > 0 && workspace.replay.ticks.length > 0,
  });
  const laps = useWorkspaceEntryLapsResource({
    entryIds,
    enabled: entryIds.length > 0,
  });
  const corners = useSessionCircuitCornersQuery(
    workspace.sessionId,
    entryIds.length > 0,
  );
  const turnMarkers = useMemo(
    () => buildTrackMapTurnMarkers(corners.data),
    [corners.data],
  );
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

    return prepareReplayTrackMapData(inputs, turnMarkers);
  }, [
    laps.dataByEntryId,
    positions.dataByEntryId,
    workspace.entries,
    entryIdsKey,
    turnMarkers,
  ]);
  const data = useMemo(
    () => prepareFrame(workspace.replay.currentTimeMs),
    [prepareFrame, workspace.replay.currentTimeMs],
  );

  if (workspace.entries.length === 0) {
    return (
      <WidgetCard title={title}>
        <WidgetEmpty message="No session entries were available for replay mode." />
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
    <WidgetCard
      title={title}
      description={`Top-down replay at ${formatSessionClock(workspace.replay.currentTimeMs)} with current-lap trails.`}
    >
      {data.outlinePoints.length === 0 && data.traces.length === 0 ? (
        <WidgetEmpty message="Position telemetry was not available for replay mode." />
      ) : (
        <TrackMapViewer data={data} mode="replay" />
      )}
    </WidgetCard>
  );
}
