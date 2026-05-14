import type {
  EntryLapDto,
  SessionEntryDto,
  SessionTrackStatusEventDto,
} from "../../../data/contracts/sessions.contracts";
import type {
  EntryLapsByEntryId,
  TrackStatusBand,
  TrackStatusKind,
} from "../models";

export function buildTrackStatusBands({
  entries,
  lapsByEntryId,
  events,
  currentTimeLimitMs,
}: {
  entries: SessionEntryDto[];
  lapsByEntryId: EntryLapsByEntryId;
  events?: SessionTrackStatusEventDto[];
  currentTimeLimitMs?: number;
}) {
  const allLaps = collectReferenceLaps(entries, lapsByEntryId, currentTimeLimitMs);

  if (events && events.length > 0 && allLaps.length > 0) {
    const eventBands = buildEventBands(events, allLaps, currentTimeLimitMs);
    if (eventBands.length > 0) {
      return eventBands;
    }
  }

  return buildLapFallbackBands(entries, lapsByEntryId, currentTimeLimitMs);
}

export function getTrackStatusKind(trackStatus: string | null): TrackStatusKind {
  if (!trackStatus || trackStatus === "1") {
    return "green";
  }

  if (/[4567]/.test(trackStatus)) {
    return "neutralized";
  }

  return "caution";
}

export function getTrackStatusLabel(trackStatus: string | null) {
  if (!trackStatus || trackStatus === "1") {
    return "Green";
  }

  if (trackStatus.includes("5")) {
    return "Red flag";
  }

  if (trackStatus.includes("4")) {
    return "Safety car";
  }

  if (trackStatus.includes("6") || trackStatus.includes("7")) {
    return "Virtual safety car";
  }

  if (trackStatus.includes("2") || trackStatus.includes("3")) {
    return "Yellow";
  }

  return `Status ${trackStatus}`;
}

export function formatTrackStatusDuration(durationMs: number | null) {
  if (durationMs == null || !Number.isFinite(durationMs)) {
    return "duration unknown";
  }

  const safe = Math.max(0, Math.floor(durationMs));
  const minutes = Math.floor(safe / 60000);
  const seconds = Math.floor((safe % 60000) / 1000);

  if (minutes > 0) {
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
  }

  return `${seconds}s`;
}

export function formatTrackStatusRange(band: TrackStatusBand) {
  const start = `L${band.lapFrom}${band.startSector ? ` ${band.startSector}` : ""}`;
  const end = `L${band.lapTo}${band.endSector ? ` ${band.endSector}` : ""}`;
  return band.lapFrom === band.lapTo && band.startSector === band.endSector ? start : `${start} -> ${end}`;
}

function buildEventBands(
  events: SessionTrackStatusEventDto[],
  allLaps: EntryLapDto[],
  currentTimeLimitMs?: number,
) {
  const sortedEvents = [...events]
    .filter((event) => currentTimeLimitMs == null || event.session_time_ms <= currentTimeLimitMs)
    .sort((left, right) => left.session_time_ms - right.session_time_ms);
  const sessionEndMs = getSessionEndMs(allLaps, currentTimeLimitMs);
  const bands: TrackStatusBand[] = [];

  for (let index = 0; index < sortedEvents.length; index += 1) {
    const event = sortedEvents[index];
    const kind = getTrackStatusKind(event.status);

    if (kind === "green") {
      continue;
    }

    const nextEvent = sortedEvents[index + 1];
    const startTimeMs = event.session_time_ms;
    const endTimeMs = nextEvent?.session_time_ms ?? sessionEndMs;
    const startLap = findLapAtTime(allLaps, startTimeMs) ?? findNearestLap(allLaps, startTimeMs);
    const endLap = findLapAtTime(allLaps, endTimeMs) ?? findNearestLap(allLaps, endTimeMs);

    if (!startLap || !endLap) {
      continue;
    }

    const startLapValue = getLapValueAtTime(startLap, startTimeMs, "start");
    const endLapValue = getLapValueAtTime(endLap, endTimeMs, "end");

    bands.push({
      key: `event:${event.id}`,
      status: event.status,
      source: "event",
      lapNumber: startLap.lap_number,
      lapFrom: startLap.lap_number,
      lapTo: endLap.lap_number,
      startLapValue,
      endLapValue: Math.max(endLapValue, startLapValue + 0.02),
      startTimeMs,
      endTimeMs,
      durationMs: endTimeMs == null ? null : Math.max(0, endTimeMs - startTimeMs),
      startSector: getSectorAtTime(startLap, startTimeMs),
      endSector: getSectorAtTime(endLap, endTimeMs),
      kind,
      label: getTrackStatusLabel(event.status),
      message: event.message,
    });
  }

  return bands;
}

function buildLapFallbackBands(
  entries: SessionEntryDto[],
  lapsByEntryId: EntryLapsByEntryId,
  currentTimeLimitMs?: number,
) {
  const bandsByLap = new Map<number, TrackStatusBand>();

  for (const entry of entries) {
    for (const lap of trimLapsForTime(lapsByEntryId[entry.id] ?? [], currentTimeLimitMs)) {
      const kind = getTrackStatusKind(lap.track_status);
      if (kind === "green") {
        continue;
      }

      const current = bandsByLap.get(lap.lap_number);
      if (!current || kind === "neutralized") {
        bandsByLap.set(lap.lap_number, {
          key: `lap:${lap.lap_number}:${lap.track_status ?? "unknown"}`,
          status: lap.track_status ?? "unknown",
          source: "lap",
          lapNumber: lap.lap_number,
          lapFrom: lap.lap_number,
          lapTo: lap.lap_number,
          startLapValue: lap.lap_number - 0.5,
          endLapValue: lap.lap_number + 0.5,
          startTimeMs: lap.lap_start_time_ms,
          endTimeMs: lap.lap_end_time_ms,
          durationMs:
            lap.lap_start_time_ms != null && lap.lap_end_time_ms != null
              ? Math.max(0, lap.lap_end_time_ms - lap.lap_start_time_ms)
              : null,
          startSector: null,
          endSector: null,
          kind,
          label: getTrackStatusLabel(lap.track_status),
          message: "Lap-level status only; exact sector not available without status events.",
        });
      }
    }
  }

  return mergeAdjacentLapBands(Array.from(bandsByLap.values()).sort((left, right) => left.lapFrom - right.lapFrom));
}

function mergeAdjacentLapBands(bands: TrackStatusBand[]) {
  const merged: TrackStatusBand[] = [];

  for (const band of bands) {
    const previous = merged[merged.length - 1];
    if (previous && previous.status === band.status && previous.lapTo + 1 === band.lapFrom) {
      previous.lapTo = band.lapTo;
      previous.endLapValue = band.endLapValue;
      previous.endTimeMs = band.endTimeMs;
      previous.durationMs =
        previous.startTimeMs != null && previous.endTimeMs != null
          ? Math.max(0, previous.endTimeMs - previous.startTimeMs)
          : previous.durationMs;
      previous.key = `${previous.key}:${band.lapTo}`;
      continue;
    }

    merged.push({ ...band });
  }

  return merged;
}

function collectReferenceLaps(
  entries: SessionEntryDto[],
  lapsByEntryId: EntryLapsByEntryId,
  currentTimeLimitMs?: number,
) {
  const selectedLaps = entries.flatMap((entry) => trimLapsForTime(lapsByEntryId[entry.id] ?? [], currentTimeLimitMs));
  const lapsByNumber = new Map<number, EntryLapDto>();

  for (const lap of selectedLaps) {
    const existing = lapsByNumber.get(lap.lap_number);
    if (!existing || getLapTimingScore(lap) > getLapTimingScore(existing)) {
      lapsByNumber.set(lap.lap_number, lap);
    }
  }

  return Array.from(lapsByNumber.values()).sort((left, right) => left.lap_number - right.lap_number);
}

function trimLapsForTime(laps: EntryLapDto[], currentTimeLimitMs?: number) {
  if (currentTimeLimitMs == null) {
    return laps;
  }

  return laps.filter(
    (lap) =>
      lap.lap_start_time_ms != null &&
      lap.lap_start_time_ms <= currentTimeLimitMs,
  );
}

function getLapTimingScore(lap: EntryLapDto) {
  return [
    lap.lap_start_time_ms,
    lap.sector_1_session_time_ms,
    lap.sector_2_session_time_ms,
    lap.sector_3_session_time_ms,
    lap.lap_end_time_ms,
  ].filter((value) => value != null).length;
}

function getSessionEndMs(laps: EntryLapDto[], currentTimeLimitMs?: number) {
  if (currentTimeLimitMs != null) {
    return currentTimeLimitMs;
  }

  const endTimes = laps.map((lap) => lap.lap_end_time_ms).filter((value): value is number => value != null);
  return endTimes.length > 0 ? Math.max(...endTimes) : null;
}

function findLapAtTime(laps: EntryLapDto[], timeMs: number | null) {
  if (timeMs == null) {
    return null;
  }

  return (
    laps.find(
      (lap) =>
        lap.lap_start_time_ms != null &&
        lap.lap_end_time_ms != null &&
        timeMs >= lap.lap_start_time_ms &&
        timeMs <= lap.lap_end_time_ms,
    ) ?? null
  );
}

function findNearestLap(laps: EntryLapDto[], timeMs: number | null) {
  if (timeMs == null || laps.length === 0) {
    return null;
  }

  return [...laps].sort((left, right) => {
    const leftTime = left.lap_start_time_ms ?? left.lap_end_time_ms ?? 0;
    const rightTime = right.lap_start_time_ms ?? right.lap_end_time_ms ?? 0;
    return Math.abs(leftTime - timeMs) - Math.abs(rightTime - timeMs);
  })[0] ?? null;
}

function getLapValueAtTime(lap: EntryLapDto, timeMs: number | null, fallback: "start" | "end") {
  if (timeMs == null || lap.lap_start_time_ms == null || lap.lap_end_time_ms == null) {
    return fallback === "start" ? lap.lap_number - 0.5 : lap.lap_number + 0.5;
  }

  const duration = Math.max(1, lap.lap_end_time_ms - lap.lap_start_time_ms);
  const progress = Math.max(0, Math.min(1, (timeMs - lap.lap_start_time_ms) / duration));
  return lap.lap_number - 0.5 + progress;
}

function getSectorAtTime(lap: EntryLapDto, timeMs: number | null) {
  if (timeMs == null) {
    return null;
  }

  if (lap.sector_1_session_time_ms != null && timeMs <= lap.sector_1_session_time_ms) {
    return "S1";
  }

  if (lap.sector_2_session_time_ms != null && timeMs <= lap.sector_2_session_time_ms) {
    return "S2";
  }

  if (
    (lap.sector_3_session_time_ms != null && timeMs <= lap.sector_3_session_time_ms) ||
    (lap.lap_end_time_ms != null && timeMs <= lap.lap_end_time_ms)
  ) {
    return "S3";
  }

  return null;
}
