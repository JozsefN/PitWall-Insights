import { useState } from "react";
import { useMembership } from "../../../data/queries/billing.queries";
import type { CircuitDefinition } from "../../../features/circuits/circuit-catalog";
import {
  useReplayTime,
  useSessionTimeLabel,
  useSessionWorkspace,
} from "../../../features/sessions/SessionWorkspaceContext";
import { resolveTrackMapLayer, trackMapLayers } from "../models";
import type {
  TrackMapData,
  TrackMapLayer,
  TrackMapMode,
  TrackMapOverlay,
  TrackMapWidgetOptions,
} from "../models";
import { TrackMapViewer } from "./TrackMapViewer";
import {
  CircuitConditionNotes,
  CircuitPitNotice,
  CircuitRoadNotice,
} from "./CircuitMapNotes";
import { useCircuitRoad } from "../hooks/use-circuit-road";
import { useCircuitPitMap } from "../hooks/use-circuit-pit-map";
import { useCircuitConditions } from "../hooks/use-circuit-conditions";
import type { MappedRoad } from "../utils/mapped-road";
import type { PitMap } from "../utils/pit-map";
import "./circuit-map-layers.css";

export function CircuitMapLayers({
  data,
  circuit,
  mode,
  options,
  lookbackFrame,
  replayFrame,
}: {
  data: TrackMapData;
  circuit?: CircuitDefinition;
  mode: TrackMapMode;
  options: TrackMapWidgetOptions;
  lookbackFrame?: { timeMs: number; label: string };
  replayFrame?: (timeMs: number, animate?: boolean) => TrackMapData;
}) {
  const [requestedLayer, setLayer] = useState<TrackMapLayer>(
    resolveTrackMapLayer(options.mapLayer),
  );
  const surfaceAccess = (useMembership().data?.plan.level ?? 0) >= 1;
  const layer = requestedLayer === "surface" && !surfaceAccess ? "track" : requestedLayer;
  const { session } = useSessionWorkspace();
  const timeLabel = useSessionTimeLabel();
  const registered = useCircuitRoad(circuit, data.outlinePoints);
  const pitMap = useCircuitPitMap();
  const conditions = useCircuitConditions(
    layer,
    surfaceAccess ? options.contextId?.trim() : undefined,
    lookbackFrame?.timeMs,
  );
  const { overlay } = conditions;

  return (
    <div className="circuit-map-layers">
      <div className="circuit-map-layers__bar">
        <div role="group" aria-label="Circuit map layers">
          {(Object.entries(trackMapLayers) as [TrackMapLayer, string][]).map(
            ([key, label]) => (
              <button
                key={key}
                type="button"
                className="track-map-control-button"
                aria-pressed={key === layer}
                disabled={key === "surface" && !surfaceAccess}
                title={key === "surface" && !surfaceAccess ? "Requires Analyst or Pro" : undefined}
                onClick={() => setLayer(key)}
              >
                {label}
              </button>
            ),
          )}
        </div>
        {conditions.asOfMs != null ? (
          <small>
            {mode === "lookback"
              ? (lookbackFrame?.label ?? "Session end")
              : "Replay"}{" "}
            · {timeLabel(conditions.asOfMs)}
            {conditions.isFetching ? " · Updating" : ""}
          </small>
        ) : null}
      </div>
      {replayFrame ? (
        <MovingReplayMap
          frame={replayFrame}
          overlay={overlay}
          seasonYear={session.season_year}
          mappedRoad={registered?.road}
          pits={pitMap.pits}
        />
      ) : (
        <TrackMapViewer
          data={data}
          mode={mode}
          overlay={overlay}
          seasonYear={session.season_year}
          mappedRoad={registered?.road}
          pits={pitMap.pits}
        />
      )}
      {conditions.status ? (
        <p className="circuit-map-layers__note" role="status">
          {conditions.status}
        </p>
      ) : null}
      <CircuitPitNotice pitMap={pitMap} />
      {layer === "track" || registered ? (
        <CircuitRoadNotice
          asset={registered?.asset}
          hasOutline={data.outlinePoints.length > 0}
        />
      ) : null}
      <CircuitConditionNotes
        overlay={overlay}
        data={data}
        hasWeatherReport={conditions.asOfMs != null}
      />
    </div>
  );
}

function MovingReplayMap({
  frame,
  overlay,
  seasonYear,
  mappedRoad,
  pits,
}: {
  frame: (timeMs: number, animate?: boolean) => TrackMapData;
  overlay: TrackMapOverlay;
  seasonYear: number;
  mappedRoad?: MappedRoad;
  pits?: PitMap;
}) {
  const timeMs = useReplayTime("frame");
  return (
    <TrackMapViewer
      data={frame(timeMs, true)}
      mode="replay"
      overlay={overlay}
      seasonYear={seasonYear}
      mappedRoad={mappedRoad}
      pits={pits}
      pitClockMs={timeMs}
    />
  );
}
