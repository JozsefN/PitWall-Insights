import type { EntryLapDto, PositionSampleDto } from "../../../data/contracts/sessions.contracts";
import type { TrackMapBounds, TrackMapPoint } from "../models";

export function sortPositionSamples(samples: PositionSampleDto[]) {
  return [...samples].sort((a, b) => {
    if (a.session_time_ms !== b.session_time_ms) {
      return a.session_time_ms - b.session_time_ms;
    }

    return a.sample_seq - b.sample_seq;
  });
}

export function groupSamplesByLap(
  samples: PositionSampleDto[],
  laps: EntryLapDto[],
) {
  const sortedSamples = sortPositionSamples(samples);
  const sortedLaps = [...laps].sort((a, b) => a.lap_number - b.lap_number);
  const lapById = new Map(sortedLaps.map((lap) => [lap.id, lap]));
  const groups = new Map<number, PositionSampleDto[]>();

  for (const sample of sortedSamples) {
    if (!hasUsablePosition(sample)) {
      continue;
    }

    const lap = resolveSampleLap(sample, sortedLaps, lapById);

    if (!lap) {
      continue;
    }

    const existing = groups.get(lap.lap_number) ?? [];
    existing.push(sample);
    groups.set(lap.lap_number, existing);
  }

  return groups;
}

export function buildPointsForLap(
  samples: PositionSampleDto[],
  lapNumber: number | null,
) {
  return samples
    .filter(hasUsablePosition)
    .map((sample): TrackMapPoint => ({
      x: Number(sample.x),
      y: Number(sample.y),
      z: sample.z == null ? null : Number(sample.z),
      sessionTimeMs: sample.session_time_ms,
      sampleSeq: sample.sample_seq,
      lapNumber,
      trackStatus: sample.track_status,
    }));
}

export function downsampleTrackPoints(points: TrackMapPoint[], maxPoints = 420) {
  if (points.length <= maxPoints) {
    return points;
  }

  const step = Math.ceil(points.length / maxPoints);
  return points.filter((_, index) => index % step === 0 || index === points.length - 1);
}

export function smoothTrackPoints(points: TrackMapPoint[], windowSize = 3) {
  if (points.length < windowSize * 2 + 1) {
    return points;
  }

  return points.map((point, index) => {
    const from = Math.max(0, index - windowSize);
    const to = Math.min(points.length - 1, index + windowSize);
    const slice = points.slice(from, to + 1);
    const x = slice.reduce((sum, item) => sum + item.x, 0) / slice.length;
    const y = slice.reduce((sum, item) => sum + item.y, 0) / slice.length;

    return {
      ...point,
      x,
      y,
    };
  });
}

export function buildTrackBounds(points: TrackMapPoint[]): TrackMapBounds {
  if (points.length === 0) {
    return {
      minX: 0,
      maxX: 100,
      minY: 0,
      maxY: 100,
      width: 100,
      height: 100,
    };
  }

  const minX = Math.min(...points.map((point) => point.x));
  const maxX = Math.max(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  const maxY = Math.max(...points.map((point) => point.y));
  const width = Math.max(maxX - minX, 100);
  const height = Math.max(maxY - minY, 100);

  return {
    minX,
    maxX,
    minY,
    maxY,
    width,
    height,
  };
}

export function buildZoomedViewBox(
  bounds: TrackMapBounds,
  zoom: number,
  focusPoint: TrackMapPoint | null,
) {
  const paddingX = Math.max(bounds.width * 0.12, 30);
  const paddingY = Math.max(bounds.height * 0.12, 30);
  const baseWidth = bounds.width + paddingX * 2;
  const baseHeight = bounds.height + paddingY * 2;
  const width = baseWidth / zoom;
  const height = baseHeight / zoom;
  const centerX = focusPoint?.x ?? bounds.minX + bounds.width / 2;
  const centerY = focusPoint?.y ?? bounds.minY + bounds.height / 2;
  const minX = clamp(centerX - width / 2, bounds.minX - paddingX, bounds.maxX + paddingX - width);
  const minY = clamp(centerY - height / 2, bounds.minY - paddingY, bounds.maxY + paddingY - height);

  return `${minX} ${minY} ${width} ${height}`;
}

export function buildPaddedBaseViewBox(bounds: TrackMapBounds) {
  const paddingX = Math.max(bounds.width * 0.12, 30);
  const paddingY = Math.max(bounds.height * 0.12, 30);

  return {
    minX: bounds.minX - paddingX,
    minY: bounds.minY - paddingY,
    width: bounds.width + paddingX * 2,
    height: bounds.height + paddingY * 2,
    centerX: bounds.minX + bounds.width / 2,
    centerY: bounds.minY + bounds.height / 2,
  };
}

export function buildViewBoxFromCenter(
  bounds: TrackMapBounds,
  zoom: number,
  center: { x: number; y: number },
) {
  const base = buildPaddedBaseViewBox(bounds);
  const width = base.width / zoom;
  const height = base.height / zoom;
  const minX = clamp(center.x - width / 2, base.minX, base.minX + base.width - width);
  const minY = clamp(center.y - height / 2, base.minY, base.minY + base.height - height);

  return {
    minX,
    minY,
    width,
    height,
  };
}

export function formatViewBox(viewBox: {
  minX: number;
  minY: number;
  width: number;
  height: number;
}) {
  return `${viewBox.minX} ${viewBox.minY} ${viewBox.width} ${viewBox.height}`;
}

export function buildTrackPath(points: TrackMapPoint[], closePath = true) {
  if (points.length === 0) {
    return "";
  }

  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");

  return closePath && shouldCloseTrackPath(points) ? `${path} Z` : path;
}

export function calculateHeadingDeg(points: TrackMapPoint[], point: TrackMapPoint | null) {
  if (!point || points.length < 2) {
    return 0;
  }

  const index = Math.max(
    0,
    points.findIndex((candidate) => candidate.sessionTimeMs === point.sessionTimeMs),
  );
  const from = points[Math.max(0, index - 2)] ?? points[0];
  const to = points[Math.min(points.length - 1, index + 2)] ?? points[points.length - 1];

  if (!from || !to) {
    return 0;
  }

  return (Math.atan2(to.y - from.y, to.x - from.x) * 180) / Math.PI;
}

export function findPointAtTime(points: TrackMapPoint[], currentTimeMs: number) {
  let candidate: TrackMapPoint | null = null;

  for (const point of points) {
    if (point.sessionTimeMs <= currentTimeMs) {
      candidate = point;
      continue;
    }

    break;
  }

  return candidate;
}

export function getTrackScale(points: TrackMapPoint[]) {
  const bounds = buildTrackBounds(points);
  return Math.max(bounds.width, bounds.height);
}

function resolveSampleLap(
  sample: PositionSampleDto,
  sortedLaps: EntryLapDto[],
  lapById: Map<string, EntryLapDto>,
) {
  if (sample.lap_id) {
    const directLap = lapById.get(sample.lap_id);

    if (directLap) {
      return directLap;
    }
  }

  return sortedLaps.find((lap) => {
    const start = lap.lap_start_time_ms;
    const end = resolveLapEndTime(lap);

    if (start == null || end == null) {
      return false;
    }

    return sample.session_time_ms >= start && sample.session_time_ms <= end;
  });
}

function hasUsablePosition(sample: PositionSampleDto) {
  if (sample.x == null || sample.y == null) {
    return false;
  }

  return Number(sample.x) !== 0 || Number(sample.y) !== 0;
}

function resolveLapEndTime(lap: EntryLapDto) {
  if (lap.lap_end_time_ms != null) {
    return lap.lap_end_time_ms;
  }

  if (lap.lap_start_time_ms != null && lap.lap_time_ms != null) {
    return lap.lap_start_time_ms + lap.lap_time_ms;
  }

  return lap.sector_3_session_time_ms;
}

function shouldCloseTrackPath(points: TrackMapPoint[]) {
  if (points.length < 3) {
    return false;
  }

  const first = points[0];
  const last = points[points.length - 1];

  if (!first || !last) {
    return false;
  }

  const bounds = buildTrackBounds(points);
  const diagonal = Math.hypot(bounds.width, bounds.height);
  const distance = Math.hypot(last.x - first.x, last.y - first.y);

  return distance <= diagonal * 0.2;
}

function clamp(value: number, min: number, max: number) {
  if (max < min) {
    return min;
  }

  return Math.min(Math.max(value, min), max);
}
