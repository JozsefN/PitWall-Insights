import { useMemo } from "react";
import {
  useWorkspaceEntryLapsResource,
  useWorkspacePositionTelemetryResource,
} from "../../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import { illustratedRoadWidthLimitM } from "../utils/track-scale";
import { sessionCircuit } from "../../../features/circuits/circuit-catalog";
import {
  getEntryAccent,
  getEntryDisplayName,
} from "../../../features/sessions/session-utils";
import { useSessionTimeBoundsQuery } from "../../../data/queries/sessions.queries";
import { sampledSessionTelemetry } from "../../../features/sessions/replay-timeline";
import { WidgetCard } from "../../shared/WidgetCard";
import {
  WidgetEmpty,
  WidgetError,
  WidgetLoading,
} from "../../shared/WidgetState";
import { CircuitMapLayers } from "../components/CircuitMapLayers";
import type { TrackMapEntryInput } from "../utils/track-map-data";
import {
  buildLookbackTrackMapData,
  pickCircuitReferenceLap,
} from "../utils/track-map-data";
import type { TrackMapWidgetOptions } from "../models";

export function SessionTrackMapWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as TrackMapWidgetOptions;
  const workspace = useSessionWorkspace();
  const circuit = sessionCircuit(workspace.session);
  const widthLimitM = illustratedRoadWidthLimitM(circuit);
  const isLapScoped = widgetOptions.scope === "lap";
  const canRequestTelemetry =
    workspace.selectedEntries.length > 0 &&
    (!isLapScoped || workspace.lapSelection !== "all");
  const selectedLap = workspace.lapSelection;
  const isWholeSession = selectedLap === "all";
  const needsTimeBounds = canRequestTelemetry && isWholeSession;
  const bounds = useSessionTimeBoundsQuery(
    workspace.sessionId,
    needsTimeBounds,
  );
  const window =
    bounds.data &&
    sampledSessionTelemetry(bounds.data.start_time_ms, bounds.data.end_time_ms);
  const positions = useWorkspacePositionTelemetryResource({
    ...(isWholeSession
      ? window
      : { scope: "lap", lapNumber: selectedLap, limit: 20_000 }),
    entryMode: "selected",
    enabled: canRequestTelemetry && (!isWholeSession || Boolean(window)),
  });
  const laps = useWorkspaceEntryLapsResource({
    entryMode: "selected",
    enabled: workspace.selectedEntries.length > 0,
  });
  const title = widgetOptions.title ?? "Track Map";
  const selectedLapFrame =
    selectedLap === "all"
      ? undefined
      : workspace.selectedEntries.flatMap((entry) => {
          const lap = laps.dataByEntryId[entry.id]?.find(
            (row) => row.lap_number === selectedLap,
          );
          return lap?.lap_end_time_ms == null
            ? []
            : [
                {
                  timeMs: lap.lap_end_time_ms,
                  label: `${entry.driver_abbreviation ?? `#${entry.car_number}`} · Lap ${selectedLap} end`,
                },
              ];
        })[0];

  const inputs = useMemo(
    (): TrackMapEntryInput[] =>
      workspace.selectedEntries.map((entry, index) => ({
        entry,
        label: getEntryDisplayName(entry),
        color: getEntryAccent(entry, index),
        samples: positions.dataByEntryId[entry.id] ?? [],
        laps: laps.dataByEntryId[entry.id] ?? [],
      })),
    [laps.dataByEntryId, positions.dataByEntryId, workspace.selectedEntries],
  );
  const lapData = useMemo(
    () => buildLookbackTrackMapData(inputs, selectedLap, widthLimitM),
    [inputs, selectedLap, widthLimitM],
  );

  const needsReference =
    canRequestTelemetry &&
    !isWholeSession &&
    positions.ready &&
    !positions.isLoading &&
    !positions.isError &&
    !lapData.outlinePoints.length;
  const referenceLap = useMemo(
    () =>
      needsReference ? pickCircuitReferenceLap(inputs, selectedLap) : undefined,
    [inputs, needsReference, selectedLap],
  );
  const reference = useWorkspacePositionTelemetryResource({
    entryIds: referenceLap ? [referenceLap.input.entry.id] : [],
    scope: "lap",
    lapNumber: referenceLap?.lap.lap_number,
    limit: 20_000,
    enabled: Boolean(referenceLap),
  });
  const data = useMemo(() => {
    if (!referenceLap || !reference.ready || reference.isLoading)
      return lapData;
    const { input, lap } = referenceLap;
    const { outlinePoints, illustratedEdges } = buildLookbackTrackMapData(
      [
        {
          ...input,
          laps: [lap],
          samples: reference.dataByEntryId[input.entry.id] ?? [],
        },
      ],
      lap.lap_number,
      widthLimitM,
    );
    return { ...lapData, outlinePoints, illustratedEdges };
  }, [
    lapData,
    referenceLap,
    reference.dataByEntryId,
    reference.isLoading,
    reference.ready,
    widthLimitM,
  ]);

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

  if (
    (needsTimeBounds && bounds.isError) ||
    positions.isError ||
    laps.isError
  ) {
    return (
      <WidgetCard title={title}>
        <WidgetError />
      </WidgetCard>
    );
  }

  if (needsTimeBounds && bounds.isLoading) {
    return (
      <WidgetCard title={title}>
        <WidgetLoading />
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
          ? "Top-down circuit outline with selected-driver racing lines."
          : `Top-down circuit outline and selected-driver racing lines for lap ${workspace.lapSelection}.`
      }
    >
      {data.outlinePoints.length === 0 && data.traces.length === 0 ? (
        <WidgetEmpty message="Track position data was not available for the selected drivers." />
      ) : (
        <CircuitMapLayers
          key={workspace.selectedLayout?.id}
          data={data}
          circuit={circuit}
          mode="lookback"
          options={widgetOptions}
          lookbackFrame={selectedLapFrame}
        />
      )}
    </WidgetCard>
  );
}
