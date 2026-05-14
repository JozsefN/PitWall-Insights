import { useMemo } from "react";
import {
  useWorkspaceEntryLapsResource,
  useWorkspacePositionTelemetryResource,
} from "../../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import {
  formatSessionClock,
  getEntryAccent,
  getEntryDisplayName,
} from "../../../features/sessions/session-utils";
import { useSessionCircuitCornersQuery } from "../../../data/queries/sessions.queries";
import { WidgetCard } from "../../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../../shared/WidgetState";
import { TrackMapViewer } from "../components/TrackMapViewer";
import { buildTrackMapTurnMarkers } from "../utils/circuit-corners";
import type { TrackMapEntryInput } from "../utils/track-map-data";
import { buildReplayTrackMapData } from "../utils/track-map-data";

export function ReplayTrackMapWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  void options;

  const workspace = useSessionWorkspace();
  const entryIds =
    workspace.selectedDriverIds.length > 0
      ? workspace.selectedDriverIds
      : workspace.entries.map((entry) => entry.id);
  const positions = useWorkspacePositionTelemetryResource({
    entryIds,
    scope: "session",
    limit: 20000,
    enabled: entryIds.length > 0,
  });
  const laps = useWorkspaceEntryLapsResource({
    entryIds,
    enabled: entryIds.length > 0,
  });
  const corners = useSessionCircuitCornersQuery(workspace.sessionId, entryIds.length > 0);
  const turnMarkers = useMemo(
    () => buildTrackMapTurnMarkers(corners.data),
    [corners.data],
  );
  const data = useMemo(() => {
    const inputs: TrackMapEntryInput[] = positions.entries.map((entry, index) => ({
      entry,
      label: getEntryDisplayName(entry),
      color: getEntryAccent(entry, index),
      samples: positions.dataByEntryId[entry.id] ?? [],
      laps: laps.dataByEntryId[entry.id] ?? [],
    }));

    return buildReplayTrackMapData(inputs, workspace.replay.currentTimeMs, turnMarkers);
  }, [laps.dataByEntryId, positions.dataByEntryId, positions.entries, turnMarkers, workspace.replay.currentTimeMs]);

  if (workspace.entries.length === 0) {
    return (
      <WidgetCard title="Replay Track Map">
        <WidgetEmpty message="No session entries were available for replay mode." />
      </WidgetCard>
    );
  }

  if (positions.isError || laps.isError) {
    return (
      <WidgetCard title="Replay Track Map">
        <WidgetError />
      </WidgetCard>
    );
  }

  if (!positions.ready) {
    return (
      <WidgetCard title="Replay Track Map">
        <WidgetEmpty message={positions.waitMessage} />
      </WidgetCard>
    );
  }

  if (positions.isLoading || laps.isLoading) {
    return (
      <WidgetCard title="Replay Track Map">
        <WidgetLoading />
      </WidgetCard>
    );
  }

  return (
    <WidgetCard
      title="Replay Track Map"
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
