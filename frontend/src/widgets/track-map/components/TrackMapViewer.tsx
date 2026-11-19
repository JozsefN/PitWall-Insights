import { DriverSelect } from "../../../components/DriverSelect";
import { driverOption } from "../../../components/driver-select-options";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type {
  TrackMapData,
  TrackMapMode,
  TrackMapOverlay,
  TrackMapPoint,
  TrackMapTrace,
} from "../models";
import {
  buildPaddedBaseViewBox,
  buildTrackBounds,
  buildTrackPath,
  buildViewBoxFromCenter,
  formatViewBox,
} from "../utils/geometry";
import { F1CarMarker } from "./F1CarMarker";
import { CircuitSurfaceOverlay, WindField } from "./CircuitMapOverlays";
import { mapOverlayColour } from "../utils/circuit-overlays";
import { smoothTrackPath } from "../utils/track-curves";
import { mapScaleBar, metresToMapUnits, replayCarDimensions } from "../utils/track-scale";
import type { MappedRoad } from "../utils/mapped-road";
import { pitPhaseAt, type PitMap } from "../utils/pit-map";
import { PitLaneDrawing } from "./PitLaneDrawing";

const ZOOM_LEVELS = [1, 1.35, 1.85, 2.8, 4.5, 7, 11, 18];
const OVERVIEW_ZOOM_LIMIT = ZOOM_LEVELS[ZOOM_LEVELS.length - 1];

type CameraTarget = "manual" | "pack" | string;

type TrackMapViewerProps = {
  data: TrackMapData;
  mode: TrackMapMode;
  seasonYear: number;
  overlay?: TrackMapOverlay;
  mappedRoad?: MappedRoad;
  pits?: PitMap;
  pitClockMs?: number;
};

type CameraPoint = {
  x: number;
  y: number;
};

type DragState = {
  pointerId: number;
  clientX: number;
  clientY: number;
  center: CameraPoint;
  unitsPerPixel: number;
};

export function TrackMapViewer({ data, mode, seasonYear, overlay, mappedRoad, pits, pitClockMs }: TrackMapViewerProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [mapSize, setMapSize] = useState({ width: 720, height: 280 });
  const [zoomIndex, setZoomIndex] = useState(0);
  const [cameraTarget, setCameraTarget] = useState<CameraTarget>("pack");
  const [manualCenter, setManualCenter] = useState<CameraPoint | null>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [showLines, setShowLines] = useState(true);
  const [showPreviousLap, setShowPreviousLap] = useState(false);
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) setMapSize({ width, height });
    });
    observer.observe(svg);
    return () => observer.disconnect();
  }, []);
  const visibleTraces = data.traces;
  const trackPoints = mappedRoad?.centre ?? data.outlinePoints;
  const bounds = useMemo(() => {
    if (trackPoints.length) return buildTrackBounds(pits ? [...trackPoints, ...pits.lane] : trackPoints);
    if (!pits) return data.fallbackBounds ?? buildTrackBounds([]);
    const fallback = data.fallbackBounds;
    return buildTrackBounds(fallback ? [
      { x: fallback.minX, y: fallback.minY },
      { x: fallback.maxX, y: fallback.maxY },
      ...pits.lane,
    ] : pits.lane);
  }, [trackPoints, data.fallbackBounds, pits]);
  const baseView = useMemo(() => buildPaddedBaseViewBox(bounds), [bounds]);
  const pitView = useMemo(() => pits ? buildPaddedBaseViewBox(buildTrackBounds(pits.lane)) : undefined, [pits]);
  const { lengthM, widthM } = replayCarDimensions(seasonYear);
  const carLength = metresToMapUnits(lengthM);
  const carWidth = metresToMapUnits(widthM);
  const fitUnitsPerPixel = Math.max(baseView.width / mapSize.width, baseView.height / mapSize.height);
  // Scale the camera to keep the smallest panels legible with the same car and road geometry.
  const closeUpCarPixels = Math.min(72, Math.max(40, Math.min(mapSize.width, mapSize.height) * 0.28));
  const closeUpZoom = Math.max(2 * OVERVIEW_ZOOM_LIMIT, closeUpCarPixels * fitUnitsPerPixel / carLength);
  const zoomLevels = mode === "replay"
    ? [...ZOOM_LEVELS, Math.sqrt(OVERVIEW_ZOOM_LIMIT * closeUpZoom), closeUpZoom]
    : ZOOM_LEVELS;
  const zoom = zoomLevels[zoomIndex] ?? 1;
  const choices = data.drivers ?? visibleTraces.map((trace) => ({
    key: trace.key,
    label: trace.entry.driver_name || trace.label,
    entry: trace.entry,
  }));
  const focused = choices.some((driver) => driver.key === cameraTarget);
  const focusingPits = cameraTarget === "pits" && pitView != null;
  const activeCameraTarget = focused || focusingPits || cameraTarget === "manual" ? cameraTarget : "pack";
  const focusedTrace = focused ? visibleTraces.find((trace) => trace.key === cameraTarget) : undefined;
  const defaultCenter = { x: baseView.centerX, y: baseView.centerY };
  const cameraCenter = focusingPits ? { x: pitView.centerX, y: pitView.centerY } : focusedTrace?.currentPoint ?? manualCenter ?? defaultCenter;
  const viewBoxObject = buildViewBoxFromCenter(bounds, zoom, cameraCenter);
  const viewBox = formatViewBox(viewBoxObject);
  const unitPerPixel = fitUnitsPerPixel / zoom;
  const dotRadius = 3.5 * unitPerPixel;
  const scaleBar = zoom >= 2.8 ? mapScaleBar(unitPerPixel) : undefined;
  const labelFontSize = 12 * unitPerPixel;
  const showCars = carLength / unitPerPixel >= 9;
  const boxCount = (focusingPits || zoom >= 4.5) && pits
    ? pits.boxes.filter(({ knownAtMs }) => pitClockMs == null || knownAtMs <= pitClockMs).length : 0;
  const smallSelection = choices.length <= 4;
  const lineTraces = mode === "lookback" || smallSelection
    ? visibleTraces
    : focusedTrace ? [focusedTrace] : [];
  const legend = smallSelection ? visibleTraces : focusedTrace ? [focusedTrace] : [];
  const canShowTrails = mode === "lookback" || smallSelection || focused;
  const labelTraces = smallSelection || zoom >= 4.5 ? visibleTraces : focusedTrace ? [focusedTrace] : [];
  const labels = placeDriverLabels(
    labelTraces, activeCameraTarget, viewBoxObject, labelFontSize, zoom >= 4.5,
    showCars ? { length: carLength, width: carWidth } : undefined,
  );

  function pitPhase(trace: TrackMapTrace) {
    return mode === "replay" && trace.currentPoint ? pitPhaseAt(pits?.byDriver.get(trace.key), trace.currentPoint.sessionTimeMs) : undefined;
  }

  const handlePointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (event.button !== 0 || zoomIndex === 0) {
      return;
    }
    const transform = event.currentTarget.getScreenCTM();
    if (!transform) return;
    const scale = Math.hypot(transform.a, transform.b);
    if (!scale) return;

    event.currentTarget.setPointerCapture(event.pointerId);
    setCameraTarget("manual");
    setManualCenter(cameraCenter);
    setDragState({
      pointerId: event.pointerId,
      clientX: event.clientX,
      clientY: event.clientY,
      center: cameraCenter,
      unitsPerPixel: 1 / scale,
    });
  };

  const handlePointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!dragState || dragState.pointerId !== event.pointerId || !svgRef.current) {
      return;
    }

    const deltaX = (event.clientX - dragState.clientX) * dragState.unitsPerPixel;
    const deltaY = (event.clientY - dragState.clientY) * dragState.unitsPerPixel;

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
    setCameraTarget("pack");
  };

  return (
    <div className="track-map-viewer">
      <div className="track-map-viewer__toolbar">
        <div className="track-map-viewer__meta" aria-label="Track map state">
          <span>{data.detail}</span>
          <span>{visibleTraces.length} {visibleTraces.length === 1 ? "driver" : "drivers"}</span>
          {zoom > 1 ? <span>{`${Math.round(zoom * 100)}% zoom`}</span> : null}
        </div>
        <div className="track-map-viewer__controls" aria-label="Track map controls">
          <label className="track-map-focus-select">
            <span>Focus</span>
            <DriverSelect
              aria-label="Focus"
              value={activeCameraTarget}
              onChange={(target) => {
                setCameraTarget(target);
                setManualCenter(null);
                if (target === "pits" && pitView) {
                  const pitUnitsPerPixel = Math.max(pitView.width / mapSize.width, pitView.height / mapSize.height);
                  const fitZoom = fitUnitsPerPixel / pitUnitsPerPixel;
                  setZoomIndex(Math.max(1, zoomLevels.findLastIndex((step) => step <= fitZoom)));
                } else {
                  setZoomIndex(target === "pack" ? 0 : target === "manual" ? zoomIndex : Math.max(zoomIndex, 2));
                }
              }}
              options={[
                ...(activeCameraTarget === "manual" ? [{ value: "manual", label: "Manual view" }] : []),
                { value: "pack", label: "Whole circuit" },
                ...(pitView ? [{ value: "pits", label: "Pit lane" }] : []),
                ...choices.map((driver) => driverOption(driver.entry, driver.key)),
              ]}
            />
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
            Fit
          </button>
          <button
            type="button"
            className="track-map-control-button"
            aria-label="Zoom in"
            title="Zoom in"
            disabled={zoomIndex === zoomLevels.length - 1}
            onClick={() => setZoomIndex((current) => Math.min(zoomLevels.length - 1, current + 1))}
          >
            +
          </button>
          <button
            type="button"
            className={`track-map-control-button${showLines && canShowTrails ? " is-active" : ""}`}
            aria-label="Show racing lines"
            aria-pressed={showLines && canShowTrails}
            disabled={!canShowTrails}
            title={canShowTrails ? "Show racing lines" : "Focus a driver to show their trail"}
            onClick={() => setShowLines((current) => !current)}
          >
            Trails
          </button>
          {mode === "replay" && focused ? (
            <button
              type="button"
              className={`track-map-control-button${showPreviousLap ? " is-active" : ""}`}
              aria-label="Show previous lap ghost"
              aria-pressed={showPreviousLap}
              title="Show previous lap ghost"
              onClick={() => setShowPreviousLap((current) => !current)}
            >
              Previous lap
            </button>
          ) : null}
        </div>
      </div>

      <div className="track-map-viewer__surface">
        <svg
          ref={svgRef}
          viewBox={viewBox}
          className={`track-map-viewer__svg${dragState ? " is-dragging" : ""}`}
          data-zoomed={zoomIndex > 0}
          aria-label="Top-down track map"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onPointerCancel={handlePointerEnd}
          onPointerLeave={handlePointerEnd}
        >
          <CircuitDrawing
            points={trackPoints}
            overlay={overlay}
            radius={dotRadius}
            closeUp={zoom >= 2.8}
            edges={mappedRoad?.edges ?? data.illustratedEdges}
            mapped={Boolean(mappedRoad)}
          />

          {showLines && showPreviousLap
            ? lineTraces.map((trace) =>
                trace.previousLapPoints.length > 1 ? (
                  <path
                    key={`${trace.key}-previous-line`}
                    d={buildTrackPath(trace.previousLapPoints, false)}
                    className="track-map-viewer__previous-line"
                    stroke={trace.color}
                    strokeWidth="1.5"
                    vectorEffect="non-scaling-stroke"
                  />
                ) : null,
              )
            : null}

          {showLines
            ? lineTraces.map((trace) =>
                trace.points.length > 1 ? (
                  <path
                    key={`${trace.key}-line`}
                    d={smoothTrackPath(trace.points, false, metresToMapUnits(0.85))}
                    className="track-map-viewer__racing-line"
                    stroke={trace.color}
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                  />
                ) : null,
              )
            : null}

          {pits ? <PitLaneDrawing data={pits} boxCount={boxCount} unitPerPixel={unitPerPixel} /> : null}
          {visibleTraces.map((trace) => {
            if (!trace.currentPoint) return null;
            const point = trace.currentPoint;
            const phase = pitPhase(trace);
            return (
              <g key={`${trace.key}-position`} data-pit-phase={phase} data-track-driver={trace.key}>
                <title>{trace.entry.driver_name || trace.label}{phase === "box" ? " · In pit box" : phase ? " · In pit lane" : ""}</title>
                {showCars ? (
                  <F1CarMarker
                    point={point}
                    headingDeg={trace.headingDeg}
                    color={trace.color}
                    label={trace.label}
                    length={carLength}
                    width={carWidth}
                  />
                ) : (
                  <circle cx={point.x} cy={point.y} r={dotRadius} fill={trace.color} className="track-map-viewer__driver-dot" />
                )}
              </g>
            );
          })}
          {labels.map((label) => <DriverLabel key={label.key} label={label} fontSize={labelFontSize} />)}
        </svg>
        {mode === "replay" && visibleTraces.length === 0 ? (
          <p className="track-map-viewer__waiting">No current car positions. Jump to a racing lap to follow the field.</p>
        ) : null}
        {overlay?.layer === "weather" && overlay.weather ? <WindField weather={overlay.weather} /> : null}
        {scaleBar ? (
          <div className="track-map-viewer__scale" title="Distance in the replay coordinate frame">
            <span>{scaleBar.metres} m</span>
            <i style={{ width: scaleBar.widthPx }} aria-hidden="true" />
          </div>
        ) : null}
      </div>

      {focusingPits && pits?.source === "pit_reports" ? <p className="track-map-pits__note">Pit lane and team markers are estimated from recorded stops.</p> : null}
      {legend.length ? <div className="track-map-viewer__legend">
        {legend.map((trace) => {
          const phase = pitPhase(trace);
          return (
            <span key={trace.key} className="track-map-driver-chip">
              <i style={{ backgroundColor: trace.color }} />
              <span>{trace.entry.driver_name || trace.label}</span>
              <small>{phase === "box" ? "In pit box" : phase ? "In pit lane" : formatTraceDetail(trace)}</small>
            </span>
          );
        })}
      </div> : null}
    </div>
  );
}

const CircuitDrawing = memo(function CircuitDrawing({
  points,
  overlay,
  radius,
  closeUp,
  edges,
  mapped,
}: {
  points: MappedRoad["centre"];
  overlay?: TrackMapOverlay;
  radius: number;
  closeUp: boolean;
  edges?: MappedRoad["edges"];
  mapped: boolean;
}) {
  const path = useMemo(() => smoothTrackPath(points, true, metresToMapUnits(1.5)), [points]);
  const road = useMemo(() => edges
    ? `${smoothTrackPath(edges.left, true, metresToMapUnits(0.6))} ${smoothTrackPath(edges.right, true, metresToMapUnits(0.6))}`
    : "", [edges]);
  const colour = mapOverlayColour(overlay);
  const hasMeasuredSurface = overlay?.layer === "surface" && overlay.surface?.zones.some(({ kind }) => kind === "racing_surface");
  const showRoad = Boolean(road) && closeUp && !hasMeasuredSurface;
  return (
    <>
      {showRoad ? (
        <path d={road} fillRule="evenodd" className="track-map-viewer__illustrated-road" data-road-source={mapped ? "mapped" : "illustrated"} vectorEffect="non-scaling-stroke" />
      ) : null}
      {path && (colour || (!showRoad && !hasMeasuredSurface)) ? (
        <path
          data-circuit-overlay={colour ? overlay?.layer : undefined}
          d={path}
          className="track-map-viewer__track-center"
          style={colour ? { stroke: colour } : undefined}
          vectorEffect="non-scaling-stroke"
        />
      ) : null}
      {overlay ? <CircuitSurfaceOverlay overlay={overlay} radius={Math.max(radius * 0.6, 3)} /> : null}
    </>
  );
});

type PlacedDriverLabel = {
  key: string;
  label: string;
  point: TrackMapPoint;
  anchorY: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

function placeDriverLabels(
  traces: TrackMapTrace[],
  focus: string,
  view: ReturnType<typeof buildViewBoxFromCenter>,
  fontSize: number,
  showNames: boolean,
  car?: { length: number; width: number },
) {
  const labels: PlacedDriverLabel[] = [];
  const center = { x: view.minX + view.width / 2, y: view.minY + view.height / 2 };
  const candidates = traces
    .filter(({ currentPoint }) =>
      currentPoint &&
      currentPoint.x >= view.minX && currentPoint.x <= view.minX + view.width &&
      currentPoint.y >= view.minY && currentPoint.y <= view.minY + view.height,
    )
    .sort((a, b) =>
      Number(b.key === focus) - Number(a.key === focus) ||
      distanceFromCenter(a.currentPoint!) - distanceFromCenter(b.currentPoint!),
    );
  function distanceFromCenter(point: TrackMapPoint) {
    return Math.hypot(point.x - center.x, point.y - center.y);
  }

  const height = fontSize * 1.55;
  for (const trace of candidates) {
    if (labels.length === 5) break;
    const point = trace.currentPoint!;
    const label = showNames ? trace.entry.driver_name || trace.label : trace.shortLabel;
    const width = Math.min(view.width * 0.75, (label.length * 0.64 + 1.2) * fontSize);
    const x = Math.min(Math.max(point.x - width / 2, view.minX + fontSize / 3), view.minX + view.width - width - fontSize / 3);
    const heading = trace.headingDeg * Math.PI / 180;
    const carHalfHeight = car ? (Math.abs(Math.sin(heading)) * car.length + Math.abs(Math.cos(heading)) * car.width) / 2 : 0;
    const anchorY = point.y - Math.max(fontSize * 0.35, carHalfHeight + fontSize * 0.15);
    for (const row of [0, 1, 2]) {
      const y = anchorY - height - fontSize * 0.35 - row * height * 1.13;
      if (y < view.minY) continue;
      const collides = labels.some((other) =>
        x < other.x + other.width + fontSize / 4 && x + width + fontSize / 4 > other.x &&
        y < other.y + other.height + fontSize / 4 && y + height + fontSize / 4 > other.y,
      );
      if (!collides) {
        labels.push({ key: trace.key, label, point, anchorY, x, y, width, height });
        break;
      }
    }
  }
  return labels;
}

function DriverLabel({ label, fontSize }: { label: PlacedDriverLabel; fontSize: number }) {
  return (
    <g className="track-map-viewer__driver-label-chip" data-entry-id={label.key} pointerEvents="none">
      <line
        x1={label.point.x} y1={label.anchorY}
        x2={label.x + label.width / 2} y2={label.y + label.height}
        strokeWidth="1" vectorEffect="non-scaling-stroke"
      />
      <rect x={label.x} y={label.y} width={label.width} height={label.height} rx={fontSize * 0.38} />
      <text x={label.x + label.width / 2} y={label.y + fontSize * 1.07} fontSize={fontSize} textAnchor="middle">
        {label.label}
      </text>
    </g>
  );
}

function formatTraceDetail(trace: TrackMapTrace) {
  const lap = trace.lapNumber == null ? trace.detail : `L${trace.lapNumber}`;
  const progress = trace.progressPct == null ? "" : ` ${Math.round(trace.progressPct)}%`;
  return `${lap}${progress}`;
}
