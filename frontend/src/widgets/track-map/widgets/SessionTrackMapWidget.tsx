import { useMemo } from "react";
import {
  useWorkspaceEntryLapsResource,
  useWorkspacePositionTelemetryResource,
} from "../../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import {
  getEntryAccent,
  getEntryDisplayName,
} from "../../../features/sessions/session-utils";
import { useSessionCircuitCornersQuery } from "../../../data/queries/sessions.queries";
import { WidgetCard } from "../../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../../shared/WidgetState";
import { TrackMapViewer } from "../components/TrackMapViewer";
import { buildTrackMapTurnMarkers } from "../utils/circuit-corners";
import type { TrackMapEntryInput } from "../utils/track-map-data";
import { buildLookbackTrackMapData } from "../utils/track-map-data";
import type { TrackMapWidgetOptions } from "../models";

export function SessionTrackMapWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as TrackMapWidgetOptions;
  const workspace = useSessionWorkspace();
  const isLapScoped = widgetOptions.scope === "lap";
  const canRequestTelemetry = workspace.selectedEntries.length > 0 && (!isLapScoped || workspace.lapSelection !== "all");
  const positions = useWorkspacePositionTelemetryResource({
    entryMode: "selected",
    scope: "session",
    limit: 20000,
    enabled: canRequestTelemetry,
  });
  const laps = useWorkspaceEntryLapsResource({
    entryMode: "selected",
    enabled: workspace.selectedEntries.length > 0,
  });
  const corners = useSessionCircuitCornersQuery(workspace.sessionId, workspace.selectedEntries.length > 0);
  const turnMarkers = useMemo(
    () => buildTrackMapTurnMarkers(corners.data),
    [corners.data],
  );
  const title = widgetOptions.title ?? "Track Map";

  const data = useMemo(() => {
    const inputs: TrackMapEntryInput[] = workspace.selectedEntries.map((entry, index) => ({
      entry,
      label: getEntryDisplayName(entry),
      color: getEntryAccent(entry, index),
      samples: positions.dataByEntryId[entry.id] ?? [],
      laps: laps.dataByEntryId[entry.id] ?? [],
    }));

    return buildLookbackTrackMapData(inputs, workspace.lapSelection, turnMarkers);
  }, [laps.dataByEntryId, positions.dataByEntryId, turnMarkers, workspace.lapSelection, workspace.selectedEntries]);

  if (workspace.selectedEntries.length === 0) {
    return (
      <WidgetCard title={title}>
        <WidgetEmpty message="Choose drivers to draw their track map overlays." />
      </WidgetCard>
    );
  }

  if (isLapScoped && workspace.lapSelection === "all") {
    return (
      <WidgetCard title={title}>
        <WidgetEmpty message="Choose a specific lap to render a lap-scoped track map." />
      </WidgetCard>
    );
  }

  if (positions.isError || laps.isError) {
    return (
      <WidgetCard title={title}>
        <WidgetError />
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
      description={
        workspace.lapSelection === "all"
          ? "Top-down circuit outline from a representative lap, with selected-driver racing lines."
          : `Top-down circuit outline and selected-driver racing lines for lap ${workspace.lapSelection}.`
      }
    >
      {data.outlinePoints.length === 0 && data.traces.length === 0 ? (
        <WidgetEmpty message="Track position data was not available for the selected drivers." />
      ) : (
        <TrackMapViewer data={data} mode="lookback" />
      )}
    </WidgetCard>
  );
}
