import { useId, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type {
  TrackMapData,
  TrackMapMode,
  TrackMapPoint,
  TrackMapTrace,
  TrackMapTurnMarker,
} from "../models";
import {
  buildPaddedBaseViewBox,
  buildTrackBounds,
  buildTrackPath,
  buildViewBoxFromCenter,
  calculateHeadingDeg,
  formatViewBox,
  getTrackScale,
} from "../utils/geometry";
import { F1CarMarker } from "./F1CarMarker";

const ZOOM_LEVELS = [1, 1.35, 1.85, 2.6, 3.6, 5];

type CameraTarget = "manual" | "pack" | string;

type TrackMapViewerProps = {
  data: TrackMapData;
  mode: TrackMapMode;
};

type CameraPoint = {
  x: number;
  y: number;
};

type ViewBox = {
  minX: number;
  minY: number;
  width: number;
  height: number;
};

type DragState = {
  pointerId: number;
  clientX: number;
  clientY: number;
  center: CameraPoint;
  viewBox: ViewBox;
};

export function TrackMapViewer({ data, mode }: TrackMapViewerProps) {
  const rawGlowFilterId = useId();
  const glowFilterId = rawGlowFilterId.replace(/:/g, "");
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [zoomIndex, setZoomIndex] = useState(0);
  const [cameraTarget, setCameraTarget] = useState<CameraTarget>(mode === "replay" ? "pack" : "manual");
  const [manualCenter, setManualCenter] = useState<CameraPoint | null>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [showLines, setShowLines] = useState(true);
  const [showPreviousLap, setShowPreviousLap] = useState(mode === "replay");
  const zoom = ZOOM_LEVELS[zoomIndex] ?? 1;
  const visibleTraces = useMemo(
    () => data.traces.filter((trace) => trace.points.length > 0 || trace.currentPoint || trace.referencePoints.length > 0),
    [data.traces],
  );
  const trackPoints = useMemo(() => {
    if (data.outlinePoints.length > 0) {
      return data.outlinePoints;
    }

    return visibleTraces
      .map((trace) => trace.referencePoints.length > 0 ? trace.referencePoints : trace.points)
      .sort((a, b) => b.length - a.length)[0] ?? [];
  }, [data.outlinePoints, visibleTraces]);
  const turnPoints = useMemo(
    () => data.turnMarkers.map((marker) => markerToPoint(marker)),
    [data.turnMarkers],
  );
  const allPoints = useMemo(
    () => [
      ...trackPoints,
      ...turnPoints,
      ...visibleTraces.flatMap((trace) => trace.referencePoints),
      ...visibleTraces.flatMap((trace) => trace.previousLapPoints),
      ...visibleTraces.flatMap((trace) => trace.points),
      ...visibleTraces.flatMap((trace) => (trace.currentPoint ? [trace.currentPoint] : [])),
    ],
    [trackPoints, turnPoints, visibleTraces],
  );
  const bounds = useMemo(() => buildTrackBounds(allPoints), [allPoints]);
  const baseView = useMemo(() => buildPaddedBaseViewBox(bounds), [bounds]);
  const defaultCenter = useMemo(
    () => ({ x: baseView.centerX, y: baseView.centerY }),
    [baseView.centerX, baseView.centerY],
  );
  const activeCameraTarget = resolveActiveCameraTarget(cameraTarget, visibleTraces, mode);
  const followedPoint = resolveCameraTargetPoint(activeCameraTarget, visibleTraces);
  const cameraCenter = followedPoint ?? manualCenter ?? defaultCenter;
  const viewBoxObject = buildViewBoxFromCenter(bounds, zoom, cameraCenter);
  const viewBox = formatViewBox(viewBoxObject);
  const scale = getTrackScale(allPoints);
  const zoomDamping = Math.sqrt(zoom);
  const trackStroke = Math.max((scale * 0.018) / zoomDamping, 20);
  const laneStroke = Math.max(trackStroke * 0.68, 14);
  const racingStroke = Math.max((scale * 0.0045) / zoomDamping, 4);
  const previousStroke = Math.max(racingStroke * 0.74, 3);
  const dotRadius = Math.max((scale * 0.008) / zoomDamping, 7);
  const carSize = Math.max((scale * 0.024) / zoomDamping, 26);
  const labelFontSize = Math.max((scale * 0.012) / zoomDamping, 13);
  const turnFontSize = Math.max((scale * 0.011) / zoomDamping, 12);
  const showCars = zoom >= 1.35;
  const trackPath = buildTrackPath(trackPoints);
  const focusedTrace = visibleTraces.find((trace) => trace.key === activeCameraTarget) ?? null;
  const lineTraces =
    activeCameraTarget !== "pack" && focusedTrace
      ? [focusedTrace, ...visibleTraces.filter((trace) => trace.key !== focusedTrace.key)]
      : visibleTraces;

  const handlePointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (event.button !== 0) {
      return;
    }

    event.currentTarget.setPointerCapture(event.pointerId);
    setCameraTarget("manual");
    setManualCenter(cameraCenter);
    setDragState({
      pointerId: event.pointerId,
      clientX: event.clientX,
      clientY: event.clientY,
      center: cameraCenter,
      viewBox: viewBoxObject,
    });
  };

  const handlePointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!dragState || dragState.pointerId !== event.pointerId || !svgRef.current) {
      return;
    }

    const rect = svgRef.current.getBoundingClientRect();
    const deltaX = rect.width > 0 ? ((event.clientX - dragState.clientX) / rect.width) * dragState.viewBox.width : 0;
    const deltaY = rect.height > 0 ? ((event.clientY - dragState.clientY) / rect.height) * dragState.viewBox.height : 0;

    setManualCenter({
      x: dragState.center.x - deltaX,
      y: dragState.center.y - deltaY,
    });
  };

  const handlePointerEnd = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (dragState?.pointerId === event.pointerId) {
      event.currentTarget.releasePointerCapture(event.pointerId);
      setDragState(null);
    }
  };

  const resetCamera = () => {
    setZoomIndex(0);
    setManualCenter(null);
    setCameraTarget(mode === "replay" ? "pack" : "manual");
  };

  return (
    <div className="track-map-viewer">
      <div className="track-map-viewer__toolbar">
        <div className="track-map-viewer__meta" aria-label="Track map state">
          <span>{data.detail}</span>
          <span>{visibleTraces.length} drivers</span>
          <span>{`${zoom.toFixed(2)}x`}</span>
        </div>
        <div className="track-map-viewer__controls" aria-label="Track map controls">
          <label className="track-map-focus-select">
            <span>Focus</span>
            <select
              value={activeCameraTarget}
              onChange={(event) => {
                setCameraTarget(event.target.value);
                setManualCenter(null);
              }}
            >
              <option value="manual">Manual</option>
              <option value="pack">Pack</option>
              {visibleTraces.map((trace) => (
                <option key={trace.key} value={trace.key}>
                  {trace.shortLabel}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="track-map-control-button"
            aria-label="Zoom out"
            title="Zoom out"
            disabled={zoomIndex === 0}
            onClick={() => setZoomIndex((current) => Math.max(0, current - 1))}
          >
            -
          </button>
          <button
            type="button"
            className="track-map-control-button"
            aria-label="Reset view"
            title="Reset view"
            disabled={zoomIndex === 0 && manualCenter == null && activeCameraTarget === (mode === "replay" ? "pack" : "manual")}
            onClick={resetCamera}
          >
            0
          </button>
          <button
            type="button"
            className="track-map-control-button"
            aria-label="Zoom in"
            title="Zoom in"
            disabled={zoomIndex === ZOOM_LEVELS.length - 1}
            onClick={() => setZoomIndex((current) => Math.min(ZOOM_LEVELS.length - 1, current + 1))}
          >
            +
          </button>
          <button
            type="button"
            className={`track-map-control-button${activeCameraTarget !== "manual" ? " is-active" : ""}`}
            aria-label="Follow selected target"
            aria-pressed={activeCameraTarget !== "manual"}
            title="Follow selected target"
            onClick={() => {
              setCameraTarget((current) => current === "manual" ? "pack" : "manual");
              setManualCenter(null);
            }}
          >
            F
          </button>
          <button
            type="button"
            className={`track-map-control-button${showLines ? " is-active" : ""}`}
            aria-label="Show racing lines"
            aria-pressed={showLines}
            title="Show racing lines"
            onClick={() => setShowLines((current) => !current)}
          >
            L
          </button>
          {mode === "replay" ? (
            <button
              type="button"
              className={`track-map-control-button${showPreviousLap ? " is-active" : ""}`}
              aria-label="Show previous lap ghost"
              aria-pressed={showPreviousLap}
              title="Show previous lap ghost"
              onClick={() => setShowPreviousLap((current) => !current)}
            >
              P
            </button>
          ) : null}
        </div>
      </div>

      <div className="track-map-viewer__surface">
        <svg
          ref={svgRef}
          viewBox={viewBox}
          className={`track-map-viewer__svg${dragState ? " is-dragging" : ""}`}
          aria-label="Top-down track map"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onPointerCancel={handlePointerEnd}
          onPointerLeave={handlePointerEnd}
        >
          <defs>
            <filter id={glowFilterId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <rect
            x={baseView.minX}
            y={baseView.minY}
            width={baseView.width}
            height={baseView.height}
            className="track-map-viewer__background"
          />

          {trackPath ? (
            <>
              <path
                d={trackPath}
                className="track-map-viewer__track-shadow"
                strokeWidth={trackStroke * 1.32}
              />
              <path
                d={trackPath}
                className="track-map-viewer__track-surface"
                strokeWidth={trackStroke}
              />
              <path
                d={trackPath}
                className="track-map-viewer__track-lane"
                strokeWidth={laneStroke}
              />
              <path
                d={trackPath}
                className="track-map-viewer__track-center"
                strokeWidth={Math.max(racingStroke * 0.38, 2)}
              />
              <StartFinishMarker points={trackPoints} strokeWidth={trackStroke} />
            </>
          ) : null}

          {data.turnMarkers.map((marker) => (
            <TurnMarker
              key={marker.key}
              marker={marker}
              fontSize={turnFontSize}
              radius={Math.max(dotRadius * 1.05, 9)}
            />
          ))}

          {showLines && showPreviousLap
            ? lineTraces.map((trace) =>
                trace.previousLapPoints.length > 1 ? (
                  <path
                    key={`${trace.key}-previous-line`}
                    d={buildTrackPath(trace.previousLapPoints, false)}
                    className="track-map-viewer__previous-line"
                    stroke={trace.color}
                    strokeWidth={previousStroke}
                  />
                ) : null,
              )
            : null}

          {showLines
            ? lineTraces.map((trace) =>
                trace.points.length > 1 ? (
                  <path
                    key={`${trace.key}-line`}
                    d={buildTrackPath(trace.points, false)}
                    className="track-map-viewer__racing-line"
                    stroke={trace.color}
                    strokeWidth={racingStroke}
                    filter={`url(#${glowFilterId})`}
                  />
                ) : null,
              )
            : null}

          {visibleTraces.map((trace, index) =>
            trace.currentPoint ? (
              <g key={`${trace.key}-position`}>
                <circle
                  cx={trace.currentPoint.x}
                  cy={trace.currentPoint.y}
                  r={dotRadius}
                  fill={trace.color}
                  className="track-map-viewer__driver-dot"
                  filter={`url(#${glowFilterId})`}
                />
                {showCars ? (
                  <F1CarMarker
                    point={trace.currentPoint}
                    headingDeg={trace.headingDeg}
                    color={trace.color}
                    label={trace.label}
                    size={carSize}
                  />
                ) : null}
                <DriverLabel
                  trace={trace}
                  index={index}
                  fontSize={labelFontSize}
                  offsetBase={dotRadius}
                  zoom={zoom}
                />
              </g>
            ) : null,
          )}
        </svg>
      </div>

      <div className="track-map-viewer__legend">
        {visibleTraces.slice(0, 12).map((trace) => (
          <span key={trace.key} className="track-map-driver-chip">
            <i style={{ backgroundColor: trace.color }} />
            <span>{trace.label}</span>
            <small>{formatTraceDetail(trace)}</small>
          </span>
        ))}
        {visibleTraces.length > 12 ? (
          <span className="track-map-driver-chip track-map-driver-chip--muted">
            +{visibleTraces.length - 12}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function StartFinishMarker({
  points,
  strokeWidth,
}: {
  points: TrackMapPoint[];
  strokeWidth: number;
}) {
  const first = points[0];
  const markerPoints = points.slice(0, 4);

  if (!first || markerPoints.length < 2) {
    return null;
  }

  const heading = calculateHeadingDeg(markerPoints, first) + 90;
  const markerLength = strokeWidth * 1.45;

  return (
    <g transform={`translate(${first.x} ${first.y}) rotate(${heading})`} className="track-map-viewer__start-finish">
      <line x1={-markerLength / 2} y1="0" x2={markerLength / 2} y2="0" strokeWidth={Math.max(strokeWidth * 0.08, 2)} />
      <text x={markerLength * 0.58} y={-strokeWidth * 0.14} fontSize={Math.max(strokeWidth * 0.42, 12)}>
        S/F
      </text>
    </g>
  );
}

function TurnMarker({
  marker,
  fontSize,
  radius,
}: {
  marker: TrackMapTurnMarker;
  fontSize: number;
  radius: number;
}) {
  const angle = ((marker.angleDeg ?? 0) * Math.PI) / 180;
  const offsetX = Math.cos(angle) * radius * 2.2;
  const offsetY = Math.sin(angle) * radius * 2.2;

  return (
    <g
      className="track-map-viewer__turn-marker"
      transform={`translate(${marker.x + offsetX} ${marker.y + offsetY})`}
    >
      <rect
        x={-radius}
        y={-radius}
        width={radius * 2}
        height={radius * 2}
        rx={Math.max(radius * 0.24, 3)}
      />
      <text y={fontSize * 0.34} fontSize={fontSize}>
        {marker.label}
      </text>
    </g>
  );
}

function DriverLabel({
  trace,
  index,
  fontSize,
  offsetBase,
  zoom,
}: {
  trace: TrackMapTrace;
  index: number;
  fontSize: number;
  offsetBase: number;
  zoom: number;
}) {
  if (!trace.currentPoint) {
    return null;
  }

  const label = trace.shortLabel;
  const width = Math.max(label.length * fontSize * 0.72 + fontSize * 1.2, fontSize * 2.8);
  const height = fontSize * 1.55;
  const offset = buildLabelOffset(index, offsetBase, zoom);

  return (
    <g
      className="track-map-viewer__driver-label-chip"
      transform={`translate(${trace.currentPoint.x + offset.x} ${trace.currentPoint.y + offset.y})`}
    >
      <rect
        x={0}
        y={-height / 2}
        width={width}
        height={height}
        rx={height * 0.34}
      />
      <text x={fontSize * 0.58} y={fontSize * 0.36} fontSize={fontSize}>
        {label}
      </text>
    </g>
  );
}

function resolveCameraTargetPoint(target: CameraTarget, traces: TrackMapTrace[]): CameraPoint | null {
  if (target === "manual") {
    return null;
  }

  if (target === "pack") {
    return getAverageCurrentPoint(traces);
  }

  const trace = traces.find((candidate) => candidate.key === target);
  return trace?.currentPoint ? { x: trace.currentPoint.x, y: trace.currentPoint.y } : null;
}

function resolveActiveCameraTarget(
  target: CameraTarget,
  traces: TrackMapTrace[],
  mode: TrackMapMode,
): CameraTarget {
  if (target === "manual" || target === "pack") {
    return target;
  }

  return traces.some((trace) => trace.key === target)
    ? target
    : mode === "replay"
      ? "pack"
      : "manual";
}

function getAverageCurrentPoint(traces: TrackMapTrace[]) {
  const points = traces
    .map((trace) => trace.currentPoint)
    .filter((point): point is TrackMapPoint => point !== null);

  if (points.length === 0) {
    return null;
  }

  const x = points.reduce((sum, point) => sum + point.x, 0) / points.length;
  const y = points.reduce((sum, point) => sum + point.y, 0) / points.length;

  return { x, y };
}

function buildLabelOffset(index: number, offsetBase: number, zoom: number) {
  const offsetDistance = offsetBase * (zoom < 1.35 ? 2.5 : 1.9);
  const angle = ((index % 8) / 8) * Math.PI * 2 - Math.PI / 5;

  return {
    x: Math.cos(angle) * offsetDistance + offsetBase * 1.2,
    y: Math.sin(angle) * offsetDistance - offsetBase * 0.6,
  };
}

function formatTraceDetail(trace: TrackMapTrace) {
  const lap = trace.lapNumber == null ? trace.detail : `L${trace.lapNumber}`;
  const progress = trace.progressPct == null ? "" : ` ${Math.round(trace.progressPct)}%`;
  return `${lap}${progress}`;
}

function markerToPoint(marker: TrackMapTurnMarker): TrackMapPoint {
  return {
    x: marker.x,
    y: marker.y,
    z: null,
    sessionTimeMs: 0,
    sampleSeq: 0,
    lapNumber: null,
    trackStatus: null,
  };
}
