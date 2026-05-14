import { useQuery } from "@tanstack/react-query";
import {
  ensureTelemetryMaterialization,
  getTelemetryMaterializationJob,
  listTelemetryMaterializationJobs,
} from "../api/telemetry-materialization.api";
import type { TelemetryMaterializationRequestDto } from "../contracts/telemetry-materialization.contracts";

const ACTIVE_STATUSES = new Set(["queued", "running"]);
const QUEUED_FAST_POLL_MS = 45_000;
const RUNNING_HEARTBEAT_TIMEOUT_MS = 10 * 60_000;

export function useEnsureTelemetryMaterializationQuery(
  request: TelemetryMaterializationRequestDto | null,
  enabled = true,
) {
  return useQuery({
    queryKey: ["telemetry-materialization", "ensure", request],
    queryFn: () => ensureTelemetryMaterialization(request as TelemetryMaterializationRequestDto),
    enabled: Boolean(request) && enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

export function useTelemetryMaterializationJobQuery(jobId?: string | null, enabled = true) {
  return useQuery({
    queryKey: ["telemetry-materialization", "jobs", jobId],
    queryFn: () => getTelemetryMaterializationJob(jobId as string),
    enabled: Boolean(jobId) && enabled,
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job || !ACTIVE_STATUSES.has(job.status)) {
        return false;
      }

      if (job.status === "queued") {
        const queuedForMs = Date.now() - new Date(job.created_at).getTime();
        return queuedForMs > QUEUED_FAST_POLL_MS ? 5000 : 1500;
      }

      const heartbeatAt = job.heartbeat_at ?? job.started_at ?? job.created_at;
      const heartbeatAgeMs = Date.now() - new Date(heartbeatAt).getTime();
      return heartbeatAgeMs > RUNNING_HEARTBEAT_TIMEOUT_MS ? false : 2500;
    },
  });
}

export function useTelemetryMaterializationJobsQuery(
  limit = 25,
  options: { refetchActive?: boolean } = {},
) {
  return useQuery({
    queryKey: ["telemetry-materialization", "jobs", limit],
    queryFn: () => listTelemetryMaterializationJobs(limit),
    refetchInterval: (query) => {
      if (!options.refetchActive) {
        return false;
      }

      const jobs = query.state.data?.jobs ?? [];
      return jobs.some((job) => ACTIVE_STATUSES.has(job.status)) ? 2000 : 3000;
    },
  });
}
