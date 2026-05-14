const TELEMETRY_WARMUP_STORAGE_PREFIX = "pitwall:telemetry-warmup-job:";
export const TELEMETRY_WARMUP_JOB_EVENT = "pitwall:telemetry-warmup-job";

export type TelemetryWarmupJobEventDetail = {
  sessionId: string;
  jobId: string | null;
};

export function writeTelemetryWarmupJobId(sessionId: string, jobId: string) {
  window.localStorage.setItem(`${TELEMETRY_WARMUP_STORAGE_PREFIX}${sessionId}`, jobId);
  dispatchTelemetryWarmupJobEvent(sessionId, jobId);
}

export function readTelemetryWarmupJobId(sessionId: string) {
  return window.localStorage.getItem(`${TELEMETRY_WARMUP_STORAGE_PREFIX}${sessionId}`);
}

export function clearTelemetryWarmupJobId(sessionId: string) {
  window.localStorage.removeItem(`${TELEMETRY_WARMUP_STORAGE_PREFIX}${sessionId}`);
  dispatchTelemetryWarmupJobEvent(sessionId, null);
}

export function getTelemetryWarmupStorageKey(sessionId: string) {
  return `${TELEMETRY_WARMUP_STORAGE_PREFIX}${sessionId}`;
}

function dispatchTelemetryWarmupJobEvent(sessionId: string, jobId: string | null) {
  window.dispatchEvent(
    new CustomEvent<TelemetryWarmupJobEventDetail>(TELEMETRY_WARMUP_JOB_EVENT, {
      detail: { sessionId, jobId },
    }),
  );
}
