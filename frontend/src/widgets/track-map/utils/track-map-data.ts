import type {
  EntryLapDto,
  PositionSampleDto,
  SessionEntryDto,
} from "../../../data/contracts/sessions.contracts";
import type { TrackMapData, TrackMapPoint, TrackMapTrace, TrackMapTurnMarker } from "../models";
import {
  buildPointsForLap,
  calculateHeadingDeg,
  downsampleTrackPoints,
  findPointAtTime,
  groupSamplesByLap,
  smoothTrackPoints,
  sortPositionSamples,
} from "./geometry";

export type TrackMapEntryInput = {
  entry: SessionEntryDto;
  label: string;
  color: string;
  samples: PositionSampleDto[];
  laps: EntryLapDto[];
};

export function buildLookbackTrackMapData(
  entries: TrackMapEntryInput[],
  selectedLap: number | "all",
  turnMarkers: TrackMapTurnMarker[] = [],
): TrackMapData {
  const traces = entries
    .map((input): TrackMapTrace | null => {
      const groups = groupSamplesByLap(input.samples, input.laps);
      const lapNumber =
        selectedLap === "all"
          ? pickRepresentativeLapNumber(input.laps, groups)
          : selectedLap;
      const rawSamples = lapNumber == null ? sortPositionSamples(input.samples) : groups.get(lapNumber) ?? [];
      const points = prepareTrackPoints(rawSamples, lapNumber, 640);
      const currentPoint = points[points.length - 1] ?? null;

      if (points.length < 2) {
        return null;
      }

      return buildTrace({
        input,
        points,
        referencePoints: points,
        previousLapPoints: [],
        currentPoint,
        headingPoints: points,
        lapNumber,
        previousLapNumber: null,
        progressPct: 100,
        detail: lapNumber == null ? "Session line" : `Lap ${lapNumber}`,
        sampleCount: rawSamples.length,
      });
    })
    .filter((trace): trace is TrackMapTrace => trace !== null);

  return {
    traces,
    outlinePoints: buildOutlinePoints(entries, selectedLap === "all" ? null : selectedLap),
    turnMarkers,
    detail: selectedLap === "all" ? "Representative lap lines" : `Lap ${selectedLap}`,
  };
}

export function buildReplayTrackMapData(
  entries: TrackMapEntryInput[],
  currentTimeMs: number,
  turnMarkers: TrackMapTurnMarker[] = [],
): TrackMapData {
  const traces = entries
    .map((input): TrackMapTrace | null => {
      const groups = groupSamplesByLap(input.samples, input.laps);
      const lapNumber = resolveCurrentLapNumber(input.laps, groups, currentTimeMs);
      const previousLapNumber = lapNumber == null ? null : lapNumber - 1;
      const currentRawSamples =
        lapNumber == null
          ? sortPositionSamples(input.samples).filter((sample) => sample.session_time_ms <= currentTimeMs)
          : groups.get(lapNumber) ?? [];
      const previousRawSamples =
        previousLapNumber == null ? [] : groups.get(previousLapNumber) ?? [];
      const referenceRawSamples =
        lapNumber != null && groups.has(lapNumber)
          ? groups.get(lapNumber) ?? []
          : resolveFirstUsableSamples(input.samples, groups, currentTimeMs);

      const referencePoints = prepareTrackPoints(referenceRawSamples, lapNumber, 760);
      const lapPoints = prepareTrackPoints(currentRawSamples, lapNumber, 760);
      const previousLapPoints = prepareTrackPoints(previousRawSamples, previousLapNumber, 520);
      const points = lapPoints.filter((point) => point.sessionTimeMs <= currentTimeMs);
      const currentPoint =
        findPointAtTime(lapPoints, currentTimeMs) ??
        points[points.length - 1] ??
        findFirstFuturePoint(referencePoints, currentTimeMs);

      if (!currentPoint && points.length < 2 && referencePoints.length < 2) {
        return null;
      }

      return buildTrace({
        input,
        points: points.length > 0 ? points : currentPoint ? [currentPoint] : [],
        referencePoints,
        previousLapPoints,
        currentPoint,
        headingPoints: lapPoints.length > 1 ? lapPoints : referencePoints,
        lapNumber,
        previousLapNumber,
        progressPct: calculateLapProgressPct(lapPoints, currentTimeMs),
        detail: lapNumber == null ? "Replay trail" : `Lap ${lapNumber}`,
        sampleCount: currentRawSamples.length,
      });
    })
    .filter((trace): trace is TrackMapTrace => trace !== null);

  const currentLapNumber =
    traces.find((trace) => trace.lapNumber != null)?.lapNumber ?? null;

  return {
    traces,
    outlinePoints: buildOutlinePoints(entries, currentLapNumber),
    turnMarkers,
    detail: currentLapNumber == null ? "Live replay" : `Lap ${currentLapNumber}`,
  };
}

function buildTrace({
  input,
  points,
  referencePoints,
  previousLapPoints,
  currentPoint,
  headingPoints,
  lapNumber,
  previousLapNumber,
  progressPct,
  detail,
  sampleCount,
}: {
  input: TrackMapEntryInput;
  points: TrackMapPoint[];
  referencePoints: TrackMapPoint[];
  previousLapPoints: TrackMapPoint[];
  currentPoint: TrackMapPoint | null;
  headingPoints: TrackMapPoint[];
  lapNumber: number | null;
  previousLapNumber: number | null;
  progressPct: number | null;
  detail: string;
  sampleCount: number;
}): TrackMapTrace {
  return {
    key: input.entry.id,
    entry: input.entry,
    label: input.label,
    shortLabel: input.entry.driver_abbreviation ?? input.entry.car_number,
    color: input.color,
    points,
    referencePoints,
    previousLapPoints,
    currentPoint,
    headingDeg: calculateHeadingDeg(headingPoints, currentPoint),
    lapNumber,
    previousLapNumber,
    progressPct,
    detail,
    sampleCount,
  };
}

function buildOutlinePoints(
  entries: TrackMapEntryInput[],
  preferredLapNumber: number | null,
) {
  const candidates = entries
    .map((input) => {
      const groups = groupSamplesByLap(input.samples, input.laps);
      const lapNumber =
        preferredLapNumber != null && groups.has(preferredLapNumber)
          ? preferredLapNumber
          : pickRepresentativeLapNumber(input.laps, groups);
      const rawSamples = lapNumber == null ? sortPositionSamples(input.samples) : groups.get(lapNumber) ?? [];
      const points = prepareTrackPoints(rawSamples, lapNumber, 880);

      return {
        points,
        score: scoreOutline(points, input.laps.find((lap) => lap.lap_number === lapNumber)),
      };
    })
    .filter((candidate) => candidate.points.length >= 8)
    .sort((a, b) => b.score - a.score);

  return candidates[0]?.points ?? [];
}

function prepareTrackPoints(
  samples: PositionSampleDto[],
  lapNumber: number | null,
  maxPoints: number,
) {
  const points = buildPointsForLap(sortPositionSamples(samples), lapNumber);
  return downsampleTrackPoints(smoothTrackPoints(points), maxPoints);
}

function pickRepresentativeLapNumber(
  laps: EntryLapDto[],
  groups: Map<number, PositionSampleDto[]>,
) {
  const candidates = [...groups.entries()]
    .map(([lapNumber, samples]) => {
      const lap = laps.find((candidate) => candidate.lap_number === lapNumber);

      return {
        lapNumber,
        score: scoreLapCandidate(lap, samples.length),
      };
    })
    .sort((a, b) => b.score - a.score || a.lapNumber - b.lapNumber);

  return candidates[0]?.lapNumber ?? null;
}

function resolveCurrentLapNumber(
  laps: EntryLapDto[],
  groups: Map<number, PositionSampleDto[]>,
  currentTimeMs: number,
) {
  const sortedLaps = [...laps]
    .filter((lap) => lap.lap_start_time_ms != null)
    .sort((a, b) => Number(a.lap_start_time_ms) - Number(b.lap_start_time_ms));
  const startedLap = sortedLaps
    .filter((lap) => Number(lap.lap_start_time_ms) <= currentTimeMs)
    .at(-1);

  if (startedLap && groups.has(startedLap.lap_number)) {
    return startedLap.lap_number;
  }

  const sampleLap = [...groups.entries()].find(([, samples]) => {
    const first = samples[0];
    const last = samples[samples.length - 1];

    if (!first || !last) {
      return false;
    }

    return currentTimeMs >= first.session_time_ms && currentTimeMs <= last.session_time_ms;
  });

  if (sampleLap) {
    return sampleLap[0];
  }

  const latestPastLap = [...groups.entries()]
    .filter(([, samples]) => {
      const first = samples[0];
      return first ? first.session_time_ms <= currentTimeMs : false;
    })
    .sort((a, b) => b[0] - a[0])[0];

  return latestPastLap?.[0] ?? null;
}

function resolveFirstUsableSamples(
  samples: PositionSampleDto[],
  groups: Map<number, PositionSampleDto[]>,
  currentTimeMs: number,
) {
  const firstFutureLap = [...groups.entries()]
    .filter(([, lapSamples]) => {
      const first = lapSamples[0];
      return first ? first.session_time_ms >= currentTimeMs : false;
    })
    .sort((a, b) => {
      const left = a[1][0]?.session_time_ms ?? Number.MAX_SAFE_INTEGER;
      const right = b[1][0]?.session_time_ms ?? Number.MAX_SAFE_INTEGER;
      return left - right;
    })[0];

  return firstFutureLap?.[1] ?? sortPositionSamples(samples);
}

function findFirstFuturePoint(points: TrackMapPoint[], currentTimeMs: number) {
  return points.find((point) => point.sessionTimeMs >= currentTimeMs) ?? points[0] ?? null;
}

function calculateLapProgressPct(points: TrackMapPoint[], currentTimeMs: number) {
  const first = points[0];
  const last = points[points.length - 1];

  if (!first || !last || last.sessionTimeMs <= first.sessionTimeMs) {
    return null;
  }

  return Math.max(
    0,
    Math.min(
      100,
      ((currentTimeMs - first.sessionTimeMs) / (last.sessionTimeMs - first.sessionTimeMs)) * 100,
    ),
  );
}

function scoreLapCandidate(lap: EntryLapDto | undefined, sampleCount: number) {
  let score = sampleCount;

  if (!lap) {
    return score;
  }

  if (lap.lap_time_ms != null) {
    score += 160;
  }

  if (lap.pit_in_time_ms != null || lap.pit_out_time_ms != null) {
    score -= 120;
  }

  if (lap.track_status && lap.track_status !== "1") {
    score -= 60;
  }

  if (lap.is_deleted || lap.is_generated || !lap.is_accurate) {
    score -= 50;
  }

  return score;
}

function scoreOutline(points: TrackMapPoint[], lap: EntryLapDto | undefined) {
  let score = points.length;

  if (lap?.lap_time_ms != null) {
    score += 120;
  }

  if (lap?.pit_in_time_ms != null || lap?.pit_out_time_ms != null) {
    score -= 100;
  }

  return score;
}
