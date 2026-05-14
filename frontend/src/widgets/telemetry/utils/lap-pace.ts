import type {
  EntryLapDto,
  SessionEntryDto,
  SessionTrackStatusEventDto,
} from "../../../data/contracts/sessions.contracts";
import { getEntryAccent, getEntryDisplayName } from "../../../features/sessions/session-utils";
import type {
  EntryLapsByEntryId,
  LapChartPoint,
  LapChartSeries,
  LapFilterState,
  LapReferenceMode,
  LapReferenceSeries,
  LapTimeAnalysis,
} from "../models";
import { buildTrackStatusBands, getTrackStatusKind } from "./track-status";

export function buildLapTimeAnalysis(
  entries: SessionEntryDto[],
  lapsByEntryId: EntryLapsByEntryId,
  filters: LapFilterState,
  trackStatusEvents: SessionTrackStatusEventDto[] = [],
): LapTimeAnalysis {
  const series = entries.map((entry, index) => {
    const rawLaps = [...(lapsByEntryId[entry.id] ?? [])]
      .filter((lap) => lap.lap_time_ms != null)
      .sort((left, right) => left.lap_number - right.lap_number);
    const outlierLapNumbers = findOutlierLapNumbers(rawLaps);
    const visiblePoints = rawLaps
      .map((lap) => buildLapPoint(entry, index, lap, outlierLapNumbers, filters))
      .filter((point): point is LapChartPoint => point != null && point.reasons.length === 0);
    const smoothedPoints = filters.smooth ? smoothLapPoints(visiblePoints) : visiblePoints;

    return {
      key: entry.id,
      entryId: entry.id,
      label: getEntryDisplayName(entry),
      color: getEntryAccent(entry, index),
      points: smoothedPoints,
    };
  });
  const allRawPoints = entries.flatMap((entry, index) => {
    const outlierLapNumbers = findOutlierLapNumbers(lapsByEntryId[entry.id] ?? []);
    return (lapsByEntryId[entry.id] ?? [])
      .map((lap) => buildLapPoint(entry, index, lap, outlierLapNumbers, filters))
      .filter((point): point is LapChartPoint => point != null);
  });
  const visiblePoints = series.flatMap((item) => item.points);
  const hiddenLapCount = allRawPoints.filter((point) => point.reasons.length > 0).length;
  const fastestPoint = visiblePoints.reduce<LapChartPoint | null>(
    (current, point) => (current == null || point.lapTimeMs < current.lapTimeMs ? point : current),
    null,
  );
  const bestMedian =
    series
      .map((item) => ({
        label: item.label,
        medianMs: median(item.points.map((point) => point.lapTimeMs)),
      }))
      .filter((item): item is { label: string; medianMs: number } => item.medianMs != null)
      .sort((left, right) => left.medianMs - right.medianMs)[0] ?? null;

  return {
    series,
    statusBands: buildTrackStatusBands({
      entries,
      lapsByEntryId,
      events: trackStatusEvents,
    }),
    visibleLapCount: visiblePoints.length,
    hiddenLapCount,
    fastestPoint,
    bestMedian,
  };
}

export function buildLapReferenceSeries(
  mode: LapReferenceMode,
  series: LapChartSeries[],
): LapReferenceSeries | null {
  if (mode === "none") {
    return null;
  }

  if (mode.startsWith("entry:")) {
    const entryId = mode.slice("entry:".length);
    const selected = series.find((item) => item.entryId === entryId);
    if (!selected || selected.points.length === 0) {
      return null;
    }

    return {
      key: `reference-${entryId}`,
      label: `${selected.label} ref`,
      color: selected.color,
      points: selected.points.map((point) => ({
        lapNumber: point.lapNumber,
        valueMs: point.chartValueMs,
      })),
    };
  }

  const grouped = new Map<number, number[]>();
  for (const point of series.flatMap((item) => item.points)) {
    grouped.set(point.lapNumber, [...(grouped.get(point.lapNumber) ?? []), point.chartValueMs]);
  }

  const points = Array.from(grouped.entries())
    .map(([lapNumber, values]) => ({
      lapNumber,
      valueMs: mode === "best" ? Math.min(...values) : average(values),
    }))
    .sort((left, right) => left.lapNumber - right.lapNumber);

  if (points.length === 0) {
    return null;
  }

  return {
    key: `reference-${mode}`,
    label: mode === "best" ? "Best visible" : "Avg visible",
    color: mode === "best" ? "var(--color-fastest-lap)" : "var(--color-accent-blue)",
    points,
  };
}

function buildLapPoint(
  entry: SessionEntryDto,
  entryIndex: number,
  lap: EntryLapDto,
  outlierLapNumbers: Set<number>,
  filters: LapFilterState,
): LapChartPoint | null {
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
    entryId: entry.id,
    label: getEntryDisplayName(entry),
    color: getEntryAccent(entry, entryIndex),
    lapNumber: lap.lap_number,
    lapTimeMs: lap.lap_time_ms,
    chartValueMs: lap.lap_time_ms,
    compound: lap.compound,
    tyreLife: lap.tyre_life,
    lapPosition: lap.lap_position,
    trackStatus: lap.track_status,
    statusKind,
    isPitLap,
    isOutlier,
    reasons,
  };
}

function smoothLapPoints(points: LapChartPoint[]) {
  return points.map((point, index) => {
    const window = points.slice(Math.max(0, index - 1), Math.min(points.length, index + 2));
    return {
      ...point,
      chartValueMs: average(window.map((item) => item.lapTimeMs)),
    };
  });
}

function findOutlierLapNumbers(laps: EntryLapDto[]) {
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

function average(values: number[]) {
  if (values.length === 0) {
    return 0;
  }

  return values.reduce((sum, value) => sum + value, 0) / values.length;
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
