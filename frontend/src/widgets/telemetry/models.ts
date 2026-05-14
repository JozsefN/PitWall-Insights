import type { EntryLapDto, SessionTrackStatusEventDto } from "../../data/contracts/sessions.contracts";

export type TelemetryMetric = "speed_kph" | "throttle_pct";

export type TelemetryWidgetOptions = {
  title?: string;
  metric?: TelemetryMetric;
  metricLabel?: string;
  unit?: string;
  requiresLap?: boolean;
  scope?: "lap" | "session";
};

export type LineSeries = {
  key: string;
  label: string;
  color: string;
  points: Array<{ x: number; y: number }>;
};

export type EntryLapsByEntryId = Record<string, EntryLapDto[]>;

export type LapFilterState = {
  cleanOnly: boolean;
  hidePitLaps: boolean;
  hideNeutralizedLaps: boolean;
  hideOutliers: boolean;
  smooth: boolean;
  showTrackStatus: boolean;
};

export type LapReferenceMode = "none" | "average" | "best" | `entry:${string}`;

export type TrackStatusKind = "green" | "caution" | "neutralized";

export type LapChartPoint = {
  entryId: string;
  label: string;
  color: string;
  lapNumber: number;
  lapTimeMs: number;
  chartValueMs: number;
  compound: string | null;
  tyreLife: number | null;
  lapPosition: number | null;
  trackStatus: string | null;
  statusKind: TrackStatusKind;
  isPitLap: boolean;
  isOutlier: boolean;
  reasons: string[];
};

export type LapChartSeries = {
  key: string;
  entryId: string;
  label: string;
  color: string;
  points: LapChartPoint[];
};

export type LapReferenceSeries = {
  key: string;
  label: string;
  color: string;
  points: Array<{ lapNumber: number; valueMs: number }>;
};

export type TrackStatusBand = {
  key: string;
  status: string;
  source: "event" | "lap";
  lapNumber: number;
  lapFrom: number;
  lapTo: number;
  startLapValue: number;
  endLapValue: number;
  startTimeMs: number | null;
  endTimeMs: number | null;
  durationMs: number | null;
  startSector: string | null;
  endSector: string | null;
  kind: Exclude<TrackStatusKind, "green">;
  label: string;
  message: string | null;
};

export type PlottedLapPoint = LapChartPoint & {
  plotX: number;
  plotY: number;
  referenceValueMs: number | null;
  deltaToReferenceMs: number | null;
};

export type LapTimeAnalysis = {
  series: LapChartSeries[];
  statusBands: TrackStatusBand[];
  visibleLapCount: number;
  hiddenLapCount: number;
  fastestPoint: LapChartPoint | null;
  bestMedian: { label: string; medianMs: number } | null;
};

export type StintFilterState = {
  cleanOnly: boolean;
  hidePitLaps: boolean;
  hideNeutralizedLaps: boolean;
  hideOutliers: boolean;
  showTrend: boolean;
  showTrackStatus: boolean;
};

export type StintLapPoint = {
  key: string;
  entryId: string;
  stintKey: string;
  driverLabel: string;
  driverColor: string;
  stintNumber: number;
  lapNumber: number;
  stintLapNumber: number;
  lapTimeMs: number;
  compound: string | null;
  tyreLife: number | null;
  lapPosition: number | null;
  trackStatus: string | null;
  statusKind: TrackStatusKind;
  isPitLap: boolean;
  isOutlier: boolean;
  reasons: string[];
  deltaFromFirstMs: number | null;
};

export type StintSeries = {
  key: string;
  entryId: string;
  driverLabel: string;
  driverColor: string;
  stintNumber: number;
  compound: string | null;
  lapFrom: number;
  lapTo: number;
  visibleLapCount: number;
  hiddenLapCount: number;
  medianLapMs: number | null;
  degradationMsPerLap: number | null;
  points: StintLapPoint[];
};

export type StintAnalysis = {
  series: StintSeries[];
  statusBands: TrackStatusBand[];
  visibleLapCount: number;
  hiddenLapCount: number;
  bestMedian: StintSeries | null;
  longestStint: StintSeries | null;
  highestDegradation: StintSeries | null;
};

export type PlottedStintPoint = StintLapPoint & {
  plotX: number;
  plotY: number;
};

export type TrackStatusContext = {
  events: SessionTrackStatusEventDto[];
};
