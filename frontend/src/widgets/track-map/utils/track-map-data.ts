import type {
  EntryLapDto,
  PositionSampleDto,
  SessionEntryDto,
} from "../../../data/contracts/sessions.contracts";
import type { TrackMapData, TrackMapPoint, TrackMapTrace } from "../models";
import {
  buildPointsForLap,
  calculateHeadingDeg,
  downsampleTrackPoints,
  buildTrackBounds,
  nextPointIndex,
  groupSamplesByLap,
  sortPositionSamples,
} from "./geometry.ts";
import { illustrateTrackEdges } from "./track-envelope.ts";
import { adjoiningFixes, prepareReplayMotion } from "./replay-motion.ts";
import { illustratedRoadWidthLimitM } from "./track-scale.ts";

export type TrackMapEntryInput = {
  entry: SessionEntryDto;
  label: string;
  color: string;
  samples: PositionSampleDto[];
  laps: EntryLapDto[];
};

type TrackLapSlices = {
  input: TrackMapEntryInput;
  groups: Map<number, PositionSampleDto[]>;
};

export function pickCircuitReferenceLap(
  entries: TrackMapEntryInput[],
  selectedLap: number,
) {
  const candidates = entries.flatMap((input) =>
    input.laps
      .filter(
        (lap) =>
          lap.lap_number !== selectedLap &&
          lap.lap_time_ms != null &&
          lap.pit_in_time_ms == null &&
          lap.pit_out_time_ms == null &&
          !lap.is_deleted &&
          !lap.is_generated,
      )
      .map((lap) => ({ input, lap })),
  );
  return candidates.sort(
    ({ lap: a }, { lap: b }) =>
      Number(b.is_accurate) - Number(a.is_accurate) ||
      Number(b.track_status === "1") - Number(a.track_status === "1") ||
      (a.lap_time_ms ?? Infinity) - (b.lap_time_ms ?? Infinity),
  )[0];
}

export function buildLookbackTrackMapData(
  entries: TrackMapEntryInput[],
  selectedLap: number | "all",
  widthLimitM = illustratedRoadWidthLimitM(),
): TrackMapData {
  const prepared = entries.map((input) => ({
    input,
    groups: groupSamplesByLap(input.samples, input.laps),
  }));
  const traces = prepared
    .map(({ input, groups }): TrackMapTrace | null => {
      const lapNumber =
        selectedLap === "all"
          ? pickRepresentativeLapNumber(input.laps, groups)
          : selectedLap;
      const rawSamples =
        lapNumber == null
          ? sortPositionSamples(input.samples)
          : (groups.get(lapNumber) ?? []);
      const points = prepareTrackPoints(rawSamples, lapNumber, 640);
      const currentPoint = points[points.length - 1] ?? null;

      if (points.length < 2) {
        return null;
      }

      return buildTrace({
        input,
        points,
        previousLapPoints: [],
        currentPoint,
        headingPoints: points,
        lapNumber,
        progressPct: 100,
        detail: lapNumber == null ? "Session line" : `Lap ${lapNumber}`,
      });
    })
    .filter((trace): trace is TrackMapTrace => trace !== null);

  return {
    traces,
    ...prepareIllustratedCircuit(prepared, widthLimitM),
    fallbackBounds: buildTrackBounds(traces.flatMap((trace) => trace.points)),
    detail:
      selectedLap === "all" ? "Representative lap lines" : `Lap ${selectedLap}`,
  };
}

// The circuit and telemetry indexes stay fixed when a frame is requested.
export function prepareReplayTrackMapData(
  entries: TrackMapEntryInput[],
  widthLimitM = illustratedRoadWidthLimitM(),
): (currentTimeMs: number, animate?: boolean) => TrackMapData {
  const prepared = entries.map((input) => {
    const groups = groupSamplesByLap(input.samples, input.laps);
    const observed = buildPointsForLap(
      sortPositionSamples(input.samples),
      null,
    );
    const laps = [...groups.entries()]
      .map(([lap, samples]) => ({
        lap,
        sessionTimeMs: samples[0].session_time_ms,
      }))
      .sort((a, b) => a.sessionTimeMs - b.sessionTimeMs);
    const lapStarts = input.laps
      .filter((lap) => lap.lap_start_time_ms != null)
      .map((lap) => ({
        sessionTimeMs: Number(lap.lap_start_time_ms),
        lap: lap.lap_number,
      }))
      .sort((a, b) => a.sessionTimeMs - b.sessionTimeMs);
    return {
      input,
      observed,
      motion: prepareReplayMotion(observed),
      groups,
      laps,
      lapStarts,
      previousPaths: new Map<number, TrackMapPoint[]>(),
    };
  });
  const { outlinePoints, illustratedEdges } = prepareIllustratedCircuit(
    prepared,
    widthLimitM,
  );
  const drivers = prepared
    .filter(({ observed }) => observed.length > 0)
    .map(({ input: { entry, label } }) => ({
      key: entry.id,
      label: entry.driver_name || label,
      entry,
    }));
  const fallbackBounds = outlinePoints.length
    ? undefined
    : buildTrackBounds(
        prepared.flatMap(({ observed }) =>
          downsampleTrackPoints(observed, 240),
        ),
      );

  return (currentTimeMs, animate = false) => {
    const traces: TrackMapTrace[] = [];
    for (const {
      input,
      observed,
      motion,
      groups,
      laps,
      lapStarts,
      previousPaths,
    } of prepared) {
      const end = nextPointIndex(observed, currentTimeMs);
      const latest = observed[end - 1];
      if (!latest || currentTimeMs - latest.sessionTimeMs > 5000) continue;

      const timedLap =
        lapStarts[nextPointIndex(lapStarts, currentTimeMs) - 1]?.lap;
      const sampledLap = laps[nextPointIndex(laps, currentTimeMs) - 1]?.lap;
      const lapNumber = timedLap ?? sampledLap ?? null;
      const previousLapNumber = lapNumber == null ? null : lapNumber - 1;
      if (previousLapNumber != null && !previousPaths.has(previousLapNumber)) {
        const samples = groups.get(previousLapNumber) ?? [];
        previousPaths.set(
          previousLapNumber,
          downsampleTrackPoints(
            buildPointsForLap(samples, previousLapNumber),
            170,
          ),
        );
      }
      const previous =
        previousLapNumber == null
          ? []
          : (previousPaths.get(previousLapNumber) ?? []);
      const previousEnd = nextPointIndex(previous, currentTimeMs);
      const marker = motion.marker(end, currentTimeMs, animate);
      const trailEnd = nextPointIndex(observed, marker.point.sessionTimeMs);
      const floor = nextPointIndex(observed, marker.point.sessionTimeMs - 8500);
      let trailStart = trailEnd - 1;
      while (
        trailStart > floor &&
        adjoiningFixes(observed[trailStart - 1], observed[trailStart])
      )
        trailStart--;
      const points = observed
        .slice(trailStart, trailEnd)
        .map((point, index) =>
          animate ? motion.pointAt(trailStart + index) : point,
        );
      if (points.at(-1)?.sessionTimeMs !== marker.point.sessionTimeMs)
        points.push(marker.point);
      traces.push({
        key: input.entry.id,
        entry: input.entry,
        label: input.label,
        shortLabel: input.entry.driver_abbreviation ?? input.entry.car_number,
        color: input.color,
        points,
        previousLapPoints:
          previousEnd === previous.length
            ? previous
            : previous.slice(0, previousEnd),
        currentPoint: marker.point,
        headingDeg: marker.heading,
        lapNumber,
        progressPct: null,
        detail: lapNumber == null ? "Replay trail" : `Lap ${lapNumber}`,
      });
    }
    const lap = traces.find((trace) => trace.lapNumber != null)?.lapNumber;
    return {
      traces,
      outlinePoints,
      illustratedEdges,
      fallbackBounds,
      drivers,
      detail: lap == null ? "Replay" : `Lap ${lap}`,
    };
  };
}

function prepareIllustratedCircuit(
  prepared: TrackLapSlices[],
  widthLimitM: number,
) {
  const outlinePoints = pickClosedOutline(prepared);
  const passes: TrackMapPoint[][] = [];
  if (outlinePoints.length) {
    let contributingDrivers = 0;
    for (const { input, groups } of prepared) {
      const clean = input.laps.filter(
        (lap) =>
          lap.track_status === "1" &&
          !lap.is_deleted &&
          lap.pit_in_time_ms == null &&
          lap.pit_out_time_ms == null &&
          (groups.get(lap.lap_number)?.length ?? 0) >= 32,
      );
      if (!clean.length) continue;
      const representative = clean.filter(
        (_, index) =>
          index === Math.floor(clean.length / 3) ||
          index === Math.floor((2 * clean.length) / 3),
      );
      for (const lap of representative) {
        passes.push(
          downsampleTrackPoints(
            buildPointsForLap(groups.get(lap.lap_number)!, lap.lap_number),
            320,
          ),
        );
      }
      if (++contributingDrivers === 8) break;
    }
  }
  return {
    outlinePoints,
    illustratedEdges: illustrateTrackEdges(outlinePoints, passes, widthLimitM),
  };
}

function pickClosedOutline(entries: TrackLapSlices[]) {
  let best: TrackMapPoint[] = [];
  let bestScore = 0;
  for (const { input, groups } of entries) {
    const timing = new Map(input.laps.map((lap) => [lap.lap_number, lap]));
    for (const [number, samples] of groups) {
      if (samples.length < 32) continue;
      const lap = timing.get(number);
      if (
        !lap?.lap_time_ms ||
        lap.pit_in_time_ms != null ||
        lap.pit_out_time_ms != null
      )
        continue;
      const duration =
        samples.at(-1)!.session_time_ms - samples[0].session_time_ms;
      if (
        duration < lap.lap_time_ms * 0.84 ||
        duration > lap.lap_time_ms * 1.16
      )
        continue;
      const points = buildPointsForLap(samples, number);
      const first = points[0];
      const last = points.at(-1)!;
      const bounds = buildTrackBounds(points);
      const diagonal = Math.hypot(bounds.width, bounds.height);
      if (!diagonal) continue;
      const closure = Math.hypot(last.x - first.x, last.y - first.y) / diagonal;
      if (closure > 0.11) continue;
      let distance = 0;
      let largestStep = 0;
      let area = 0;
      const centerX = bounds.minX + bounds.width / 2;
      const centerY = bounds.minY + bounds.height / 2;
      for (let index = 0; index < points.length; index++) {
        const from = points[index];
        const to = points[(index + 1) % points.length];
        const step = Math.hypot(to.x - from.x, to.y - from.y);
        distance += step;
        largestStep = Math.max(largestStep, step);
        // The two lobes of a figure eight can cancel in a signed polygon area.
        area += Math.abs(
          (from.x - centerX) * (to.y - centerY) -
            (to.x - centerX) * (from.y - centerY),
        );
      }
      if (
        largestStep > diagonal * 0.18 ||
        distance < diagonal * 1.9 ||
        area < bounds.width * bounds.height * 0.12
      )
        continue;
      const clean = lap.track_status === "1" ? 1.12 : 1;
      const score = diagonal * clean * (1 - closure - largestStep / diagonal);
      if (score > bestScore) {
        bestScore = score;
        best = points;
      }
    }
  }
  return downsampleTrackPoints(best, 480);
}

function buildTrace({
  input,
  points,
  previousLapPoints,
  currentPoint,
  headingPoints,
  lapNumber,
  progressPct,
  detail,
}: {
  input: TrackMapEntryInput;
  points: TrackMapPoint[];
  previousLapPoints: TrackMapPoint[];
  currentPoint: TrackMapPoint | null;
  headingPoints: TrackMapPoint[];
  lapNumber: number | null;
  progressPct: number | null;
  detail: string;
}): TrackMapTrace {
  return {
    key: input.entry.id,
    entry: input.entry,
    label: input.label,
    shortLabel: input.entry.driver_abbreviation ?? input.entry.car_number,
    color: input.color,
    points,
    previousLapPoints,
    currentPoint,
    headingDeg: calculateHeadingDeg(headingPoints, currentPoint),
    lapNumber,
    progressPct,
    detail,
  };
}

function prepareTrackPoints(
  samples: PositionSampleDto[],
  lapNumber: number | null,
  maxPoints: number,
) {
  const points = buildPointsForLap(sortPositionSamples(samples), lapNumber);
  return downsampleTrackPoints(points, maxPoints);
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
