import { useSyncExternalStore } from "react";
import {
  getTelemetryWarmupStorageKey,
  readTelemetryWarmupJobId,
  TELEMETRY_WARMUP_JOB_EVENT,
  type TelemetryWarmupJobEventDetail,
} from "./session-import-warmup";

export function useTelemetryWarmupJobId(sessionId?: string) {
  return useSyncExternalStore(
    (onStoreChange) => {
      if (!sessionId || typeof window === "undefined") {
        return () => undefined;
      }

      const activeSessionId = sessionId;

      function handleTelemetryWarmupJob(event: Event) {
        const detail = (event as CustomEvent<TelemetryWarmupJobEventDetail>)
          .detail;

        if (detail?.sessionId === activeSessionId) {
          onStoreChange();
        }
      }

      function handleStorage(event: StorageEvent) {
        if (event.key === getTelemetryWarmupStorageKey(activeSessionId)) {
          onStoreChange();
        }
      }

      window.addEventListener(
        TELEMETRY_WARMUP_JOB_EVENT,
        handleTelemetryWarmupJob,
      );
      window.addEventListener("storage", handleStorage);

      return () => {
        window.removeEventListener(
          TELEMETRY_WARMUP_JOB_EVENT,
          handleTelemetryWarmupJob,
        );
        window.removeEventListener("storage", handleStorage);
      };
    },
    () => (sessionId ? readTelemetryWarmupJobId(sessionId) : null),
    () => null,
  );
}
