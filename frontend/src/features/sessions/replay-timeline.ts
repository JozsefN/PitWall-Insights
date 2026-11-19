import type { SessionTickDto } from "../../data/contracts/sessions.contracts";

export function formatReplayElapsed(timeMs: number, startMs: number) {
  const seconds = Math.max(0, Math.floor((timeMs - startMs) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds / 60) % 60;
  const remainder = String(seconds % 60).padStart(2, "0");
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, "0")}:${remainder}`
    : `${minutes}:${remainder}`;
}

// Playback needs a clock, not tens of thousands of raw telemetry tick records.
export function buildReplayClock(start: number, end: number): SessionTickDto[] {
  if (end < start || !Number.isFinite(start) || !Number.isFinite(end))
    return [];
  const step = Math.max(1000, Math.ceil((end - start) / 20000 / 1000) * 1000);
  const times = Array.from(
    { length: Math.floor((end - start) / step) + 1 },
    (_, index) => start + index * step,
  );
  if (times.at(-1) !== end) times.push(end);
  return times.map((time, index) => ({
    id: `replay:${time}`,
    tick_no: index + 1,
    session_time_ms: time,
    source_time_utc: null,
    source_kind: "replay-clock",
  }));
}

function replaySampleInterval(start: number, end: number): number {
  return Math.max(500, Math.ceil(Math.max(0, end - start) / 18000 / 100) * 100);
}

export function sampledSessionTelemetry(start: number, end: number) {
  return {
    scope: "session" as const,
    limit: 20_000,
    sampleIntervalMs: replaySampleInterval(start, end),
    sessionTimeFromMs: start,
    sessionTimeToMs: end > start ? end : undefined,
  };
}
