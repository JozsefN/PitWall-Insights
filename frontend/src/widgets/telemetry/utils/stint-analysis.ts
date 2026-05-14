import type {
  EntryLapDto,
  SessionEntryDto,
  SessionTrackStatusEventDto,
} from "../../../data/contracts/sessions.contracts";
import { getEntryAccent, getEntryDisplayName } from "../../../features/sessions/session-utils";
import type {
  EntryLapsByEntryId,
  StintAnalysis,
  StintFilterState,
  StintLapPoint,
  StintSeries,
} from "../models";
import {
  buildTrackStatusBands,
  getTrackStatusKind,
  getTrackStatusLabel,
} from "./track-status";

export function buildStintAnalysis(
  entries: SessionEntryDto[],
  lapsByEntryId: EntryLapsByEntryId,
  filters: StintFilterState,
  currentTimeLimitMs?: number,
  trackStatusEvents: SessionTrackStatusEventDto[] = [],
): StintAnalysis {
  const series = entries.flatMap((entry, index) => {
    const entryLaps = trimLapsForReplay(lapsByEntryId[entry.id] ?? [], currentTimeLimitMs);
    const grouped = groupLapsByStint(entryLaps);

    return Array.from(grouped.entries())
      .map(([stintNumber, laps]) => buildStintSeries(entry, index, stintNumber, laps, filters))
      .filter((stint): stint is StintSeries => stint != null);
  });
  const visibleLapCount = series.reduce((sum, stint) => sum + stint.visibleLapCount, 0);
  const hiddenLapCount = series.reduce((sum, stint) => sum + stint.hiddenLapCount, 0);
  const medianCandidates = series.filter((stint) => stint.medianLapMs != null);
  const degradationCandidates = series.filter(
    (stint) => stint.degradationMsPerLap != null && stint.degradationMsPerLap > 0,
  );

  return {
    series,
    statusBands: buildTrackStatusBands({
      entries,
      lapsByEntryId,
      events: trackStatusEvents,
      currentTimeLimitMs,
    }),
    visibleLapCount,
    hiddenLapCount,
    bestMedian:
      [...medianCandidates].sort(
        (left, right) => Number(left.medianLapMs) - Number(right.medianLapMs),
      )[0] ?? null,
    longestStint:
      [...series].sort(
        (left, right) => right.lapTo - right.lapFrom - (left.lapTo - left.lapFrom),
      )[0] ?? null,
    highestDegradation:
      [...degradationCandidates].sort(
        (left, right) => Number(right.degradationMsPerLap) - Number(left.degradationMsPerLap),
      )[0] ?? null,
  };
}

export function getCompoundLabel(compound: string | null) {
  if (!compound) {
    return "Unknown";
  }

  const normalized = compound.toLowerCase();
  if (normalized.includes("soft")) {
    return "Soft";
  }
  if (normalized.includes("medium")) {
    return "Medium";
  }
  if (normalized.includes("hard")) {
    return "Hard";
  }
  if (normalized.includes("inter")) {
    return "Intermediate";
  }
  if (normalized.includes("wet")) {
    return "Wet";
  }

  return compound;
}

export function getCompoundShortLabel(compound: string | null) {
  const label = getCompoundLabel(compound);
  if (label === "Intermediate") {
    return "I";
  }
  if (label === "Unknown") {
    return "?";
  }
  return label.slice(0, 1).toUpperCase();
}

export function getCompoundColor(compound: string | null) {
  const label = getCompoundLabel(compound);
  if (label === "Soft") {
    return "#ef4444";
  }
  if (label === "Medium") {
    return "#facc15";
  }
  if (label === "Hard") {
    return "#f8fafc";
  }
  if (label === "Intermediate") {
    return "#22c55e";
  }
  if (label === "Wet") {
    return "#1e90ff";
  }
  return "#8b95a7";
}

export function formatDegradation(valueMsPerLap: number | null) {
  if (valueMsPerLap == null || !Number.isFinite(valueMsPerLap)) {
    return "N/A";
  }

  const sign = valueMsPerLap >= 0 ? "+" : "-";
  return `${sign}${(Math.abs(valueMsPerLap) / 1000).toFixed(3)}s/lap`;
}

export function getStintStatusLabel(trackStatus: string | null) {
  return getTrackStatusLabel(trackStatus);
}

function buildStintSeries(
  entry: SessionEntryDto,
  entryIndex: number,
  stintNumber: number,
  laps: EntryLapDto[],
  filters: StintFilterState,
): StintSeries | null {
  const timedLaps = [...laps]
    .filter((lap) => lap.lap_time_ms != null)
    .sort((left, right) => left.lap_number - right.lap_number);

  if (timedLaps.length === 0) {
    return null;
  }

  const outlierLapNumbers = findStintOutlierLapNumbers(timedLaps);
  const driverLabel = getEntryDisplayName(entry);
  const driverColor = getEntryAccent(entry, entryIndex);
  const firstLapNumber = Math.min(...laps.map((lap) => lap.lap_number));
  const rawPoints = timedLaps
    .map((lap) =>
      buildStintPoint({
        entry,
        driverLabel,
        driverColor,
        stintNumber,
        firstLapNumber,
        lap,
        outlierLapNumbers,
        filters,
      }),
    )
    .filter((point): point is StintLapPoint => point != null);
  const points = rawPoints.filter((point) => point.reasons.length === 0);
  const firstVisibleLapTimeMs = points[0]?.lapTimeMs ?? null;
  const pointsWithDelta = points.map((point) => ({
    ...point,
    deltaFromFirstMs: firstVisibleLapTimeMs == null ? null : point.lapTimeMs - firstVisibleLapTimeMs,
  }));
  const compound = pickRepresentativeCompound(laps);

  return {
    key: `${entry.id}:stint:${stintNumber}`,
    entryId: entry.id,
    driverLabel,
    driverColor,
    stintNumber,
    compound,
    lapFrom: Math.min(...laps.map((lap) => lap.lap_number)),
    lapTo: Math.max(...laps.map((lap) => lap.lap_number)),
    visibleLapCount: pointsWithDelta.length,
    hiddenLapCount: rawPoints.length - pointsWithDelta.length,
    medianLapMs: median(pointsWithDelta.map((point) => point.lapTimeMs)),
    degradationMsPerLap: calculateSlope(pointsWithDelta),
    points: pointsWithDelta,
  };
}

function buildStintPoint({
  entry,
  driverLabel,
  driverColor,
  stintNumber,
  firstLapNumber,
  lap,
  outlierLapNumbers,
  filters,
}: {
  entry: SessionEntryDto;
  driverLabel: string;
  driverColor: string;
  stintNumber: number;
  firstLapNumber: number;
  lap: EntryLapDto;
  outlierLapNumbers: Set<number>;
  filters: StintFilterState;
}): StintLapPoint | null {
  if (lap.lap_time_ms == null) {
    return null;
  }

  const statusKind = getTrackStatusKind(lap.track_status);
  const isPitLap = lap.pit_in_time_ms != null || lap.pit_out_time_ms != null;
  const isOutlier = outlierLapNumbers.has(lap.lap_number);
  const reasons: string[] = [];

  if (filters.cleanOnly && (lap.is_deleted || lap.is_generated || !lap.is_accurate)) {
    reasons.push("not clean");
  }

  if (filters.hidePitLaps && isPitLap) {
    reasons.push("pit");
  }

  if (filters.hideNeutralizedLaps && statusKind === "neutralized") {
    reasons.push("SC/VSC");
  }

  if (filters.hideOutliers && isOutlier) {
    reasons.push("outlier");
  }

  return {
    key: `${entry.id}:${stintNumber}:${lap.lap_number}`,
    entryId: entry.id,
    stintKey: `${entry.id}:stint:${stintNumber}`,
    driverLabel,
    driverColor,
    stintNumber,
    lapNumber: lap.lap_number,
    stintLapNumber: lap.lap_number - firstLapNumber + 1,
    lapTimeMs: lap.lap_time_ms,
    compound: lap.compound,
    tyreLife: lap.tyre_life,
    lapPosition: lap.lap_position,
    trackStatus: lap.track_status,
    statusKind,
    isPitLap,
    isOutlier,
    reasons,
    deltaFromFirstMs: null,
  };
}

function groupLapsByStint(laps: EntryLapDto[]) {
  const grouped = new Map<number, EntryLapDto[]>();
  for (const lap of laps) {
    const stintNumber = lap.stint_number ?? 1;
    grouped.set(stintNumber, [...(grouped.get(stintNumber) ?? []), lap]);
  }
  return grouped;
}

function trimLapsForReplay(laps: EntryLapDto[], currentTimeLimitMs?: number) {
  if (currentTimeLimitMs == null) {
    return laps;
  }

  return laps.filter(
    (lap) => lap.lap_end_time_ms != null && lap.lap_end_time_ms <= currentTimeLimitMs,
  );
}

function findStintOutlierLapNumbers(laps: EntryLapDto[]) {
  const normalLaps = laps.filter(
    (lap) =>
      lap.lap_time_ms != null &&
      !lap.is_deleted &&
      !lap.is_generated &&
      lap.is_accurate &&
      lap.pit_in_time_ms == null &&
      lap.pit_out_time_ms == null &&
      getTrackStatusKind(lap.track_status) !== "neutralized",
  );
  const times = normalLaps.map((lap) => Number(lap.lap_time_ms));
  const center = median(times);

  if (center == null || times.length < 5) {
    return new Set<number>();
  }

  const deviations = times.map((value) => Math.abs(value - center));
  const mad = median(deviations) ?? 0;
  const threshold = Math.max(3000, mad * 4);

  return new Set(
    normalLaps
      .filter((lap) => lap.lap_time_ms != null && Math.abs(lap.lap_time_ms - center) > threshold)
      .map((lap) => lap.lap_number),
  );
}

function pickRepresentativeCompound(laps: EntryLapDto[]) {
  const counts = new Map<string, number>();
  for (const lap of laps) {
    if (!lap.compound) {
      continue;
    }
    counts.set(lap.compound, (counts.get(lap.compound) ?? 0) + 1);
  }

  return [...counts.entries()].sort((left, right) => right[1] - left[1])[0]?.[0] ?? null;
}

function calculateSlope(points: StintLapPoint[]) {
  if (points.length < 2) {
    return null;
  }

  const count = points.length;
  const sumX = points.reduce((sum, point) => sum + point.lapNumber, 0);
  const sumY = points.reduce((sum, point) => sum + point.lapTimeMs, 0);
  const sumXY = points.reduce((sum, point) => sum + point.lapNumber * point.lapTimeMs, 0);
  const sumXX = points.reduce((sum, point) => sum + point.lapNumber * point.lapNumber, 0);
  const denominator = count * sumXX - sumX * sumX;

  if (denominator === 0) {
    return null;
  }

  return (count * sumXY - sumX * sumY) / denominator;
}

function median(values: number[]) {
  if (values.length === 0) {
    return null;
  }

  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);

  if (sorted.length % 2 === 0) {
    return (sorted[middle - 1] + sorted[middle]) / 2;
  }

  return sorted[middle];
}
