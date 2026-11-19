import type { SessionEntryDto } from "../../data/contracts/sessions.contracts";
import type { IllustratedTrackEdges } from "./utils/track-envelope";
import type {
  ReviewData,
  WeatherPoint,
} from "../../features/session-review/contracts";

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
  previousLapPoints: TrackMapPoint[];
  currentPoint: TrackMapPoint | null;
  headingDeg: number;
  lapNumber: number | null;
  progressPct: number | null;
  detail: string;
};

export type TrackMapData = {
  traces: TrackMapTrace[];
  outlinePoints: TrackMapPoint[];
  detail: string;
  fallbackBounds?: TrackMapBounds;
  illustratedEdges?: IllustratedTrackEdges;
  drivers?: { key: string; label: string; entry: SessionEntryDto }[];
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

export const trackMapLayers = {
  track: "Track",
  weather: "Wind & rain",
  flags: "Flags",
  surface: "Surface & recovery",
} as const;
export type TrackMapLayer = keyof typeof trackMapLayers;

export function resolveTrackMapLayer(value: unknown): TrackMapLayer {
  return typeof value === "string" && Object.hasOwn(trackMapLayers, value)
    ? (value as TrackMapLayer)
    : "track";
}

export type TrackMapOverlay = {
  layer: TrackMapLayer;
  weather?: WeatherPoint | null;
  flags?: ReviewData["groups"]["flags"];
  surface?: ReviewData["groups"]["surface"];
};

export type TrackMapWidgetOptions = {
  title?: string;
  scope?: "session" | "lap";
  mapLayer?: TrackMapLayer;
  contextId?: string;
};
