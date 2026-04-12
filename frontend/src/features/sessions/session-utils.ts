import type {
  CarTelemetrySampleDto,
  EntryLapDto,
  PositionSampleDto,
  SessionEntryDto,
  SessionTickDto,
} from "../../data/contracts/sessions.contracts";

export type ChartPoint = {
  x: number;
  y: number;
};

export type ReplayPosition = {
  entry: SessionEntryDto;
  sample: PositionSampleDto;
};

export function formatEventSessionLabel(eventName: string, sessionName: string) {
  return `${eventName} - ${sessionName}`;
}

export function formatDateTime(value?: string | null) {
  if (!value) {
    return "TBD";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "TBD";
  }

  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatSessionClock(totalMs: number | null | undefined) {
  if (totalMs == null || !Number.isFinite(totalMs)) {
    return "--:--.---";
  }

  const safe = Math.max(0, Math.floor(totalMs));
  const minutes = Math.floor(safe / 60000);
  const seconds = Math.floor((safe % 60000) / 1000);
  const milliseconds = safe % 1000;

  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(milliseconds).padStart(3, "0")}`;
}

export function formatLapTime(totalMs: number | null | undefined) {
  if (totalMs == null || !Number.isFinite(totalMs)) {
    return "--:--.---";
  }

  const safe = Math.max(0, Math.floor(totalMs));
  const minutes = Math.floor(safe / 60000);
  const seconds = Math.floor((safe % 60000) / 1000);
  const milliseconds = safe % 1000;

  return `${minutes}:${String(seconds).padStart(2, "0")}.${String(milliseconds).padStart(3, "0")}`;
}

export function getEntryDisplayName(entry: SessionEntryDto) {
  return entry.driver_abbreviation || entry.driver_name || `#${entry.car_number}`;
}

export function getEntryAccent(entry: SessionEntryDto, index = 0) {
  const fallback = ["#ff5b4d", "#4db5ff", "#ffcf5d", "#5ef2a2", "#d07cff", "#f98d54"];
  return entry.team_color ? `#${entry.team_color.replace(/^#/, "")}` : fallback[index % fallback.length];
}

export function buildMetricChartPoints(
  samples: CarTelemetrySampleDto[],
  metric: "speed_kph" | "throttle_pct",
): ChartPoint[] {
  return samples
    .filter((sample) => sample[metric] != null)
    .map((sample) => ({
      x: sample.session_time_ms,
      y: Number(sample[metric]),
    }));
}

export function buildBrakePoints(samples: CarTelemetrySampleDto[]): ChartPoint[] {
  return samples
    .filter((sample) => sample.brake_on != null)
    .map((sample) => ({
      x: sample.session_time_ms,
      y: sample.brake_on ? 100 : 0,
    }));
}

export function buildLapTrendPoints(laps: EntryLapDto[]): ChartPoint[] {
  return laps
    .filter((lap) => lap.lap_time_ms != null)
    .map((lap) => ({
      x: lap.lap_number,
      y: Number(lap.lap_time_ms),
    }));
}

export function buildTrackPoints(samples: PositionSampleDto[]): ChartPoint[] {
  return samples
    .filter((sample) => sample.x != null && sample.y != null)
    .map((sample) => ({
      x: Number(sample.x),
      y: Number(sample.y),
    }));
}

export function downsamplePoints(points: ChartPoint[], maxPoints = 180): ChartPoint[] {
  if (points.length <= maxPoints) {
    return points;
  }

  const step = Math.ceil(points.length / maxPoints);
  return points.filter((_, index) => index % step === 0 || index === points.length - 1);
}

export function buildLinePath(points: ChartPoint[], width: number, height: number) {
  if (points.length === 0) {
    return "";
  }

  const minX = Math.min(...points.map((point) => point.x));
  const maxX = Math.max(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  const maxY = Math.max(...points.map((point) => point.y));

  return points
    .map((point, index) => {
      const x = scaleValue(point.x, minX, maxX, 12, width - 12);
      const y = scaleValue(point.y, minY, maxY, height - 16, 12);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export function buildReplayTrackViewBox(points: ChartPoint[]) {
  if (points.length === 0) {
    return "0 0 100 100";
  }

  const minX = Math.min(...points.map((point) => point.x));
  const maxX = Math.max(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  const maxY = Math.max(...points.map((point) => point.y));
  const paddingX = Math.max((maxX - minX) * 0.08, 20);
  const paddingY = Math.max((maxY - minY) * 0.08, 20);

  return `${minX - paddingX} ${minY - paddingY} ${Math.max(maxX - minX + paddingX * 2, 100)} ${Math.max(maxY - minY + paddingY * 2, 100)}`;
}

export function findTelemetrySampleAtTime(
  samples: CarTelemetrySampleDto[],
  currentTimeMs: number,
) {
  let candidate: CarTelemetrySampleDto | null = null;

  for (const sample of samples) {
    if (sample.session_time_ms <= currentTimeMs) {
      candidate = sample;
      continue;
    }
    break;
  }

  return candidate;
}

export function findPositionSampleAtTime(
  samples: PositionSampleDto[],
  currentTimeMs: number,
) {
  let candidate: PositionSampleDto | null = null;

  for (const sample of samples) {
    if (sample.session_time_ms <= currentTimeMs) {
      candidate = sample;
      continue;
    }
    break;
  }

  return candidate;
}

export function findTickAtTime(
  ticks: SessionTickDto[],
  currentTimeMs: number,
) {
  let candidate: SessionTickDto | null = null;

  for (const tick of ticks) {
    if (tick.session_time_ms <= currentTimeMs) {
      candidate = tick;
      continue;
    }
    break;
  }

  return candidate;
}

function scaleValue(
  value: number,
  domainMin: number,
  domainMax: number,
  rangeMin: number,
  rangeMax: number,
) {
  if (domainMin === domainMax) {
    return (rangeMin + rangeMax) / 2;
  }

  const progress = (value - domainMin) / (domainMax - domainMin);
  return rangeMin + progress * (rangeMax - rangeMin);
}

