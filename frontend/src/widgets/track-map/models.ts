import type { SessionEntryDto } from "../../data/contracts/sessions.contracts";

export type TrackMapPoint = {
  x: number;
  y: number;
  z: number | null;
  sessionTimeMs: number;
  sampleSeq: number;
  lapNumber: number | null;
  trackStatus: string | null;
};

export type TrackMapTrace = {
  key: string;
  entry: SessionEntryDto;
  label: string;
  shortLabel: string;
  color: string;
  points: TrackMapPoint[];
  referencePoints: TrackMapPoint[];
  previousLapPoints: TrackMapPoint[];
  currentPoint: TrackMapPoint | null;
  headingDeg: number;
  lapNumber: number | null;
  previousLapNumber: number | null;
  progressPct: number | null;
  detail: string;
  sampleCount: number;
};

export type TrackMapTurnMarker = {
  key: string;
  label: string;
  x: number;
  y: number;
  angleDeg: number | null;
  distanceM: number | null;
};

export type TrackMapData = {
  traces: TrackMapTrace[];
  outlinePoints: TrackMapPoint[];
  turnMarkers: TrackMapTurnMarker[];
  detail: string;
};

export type TrackMapBounds = {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  width: number;
  height: number;
};

export type TrackMapMode = "lookback" | "replay";

export type TrackMapWidgetOptions = {
  title?: string;
  scope?: "session" | "lap";
};
