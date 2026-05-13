import { useMutation, useQuery } from "@tanstack/react-query";
import { createImportJob, getImportJob, listImportJobs } from "../api/session-import.api";
import type { SessionImportRequestDto } from "../contracts/sessions.contracts";

const ACTIVE_IMPORT_STATUSES = new Set(["queued", "running"]);
const QUEUED_JOB_POLL_TIMEOUT_MS = 45_000;
const RUNNING_JOB_HEARTBEAT_TIMEOUT_MS = 10 * 60_000;

export function useImportJobsQuery(limit = 25) {
  return useQuery({
    queryKey: ["session-import", "jobs", limit],
    queryFn: () => listImportJobs(limit),
  });
}

export function useImportJobQuery(jobId?: string, enabled = true) {
  return useQuery({
    queryKey: ["session-import", "jobs", jobId],
    queryFn: () => getImportJob(jobId as string),
    enabled: Boolean(jobId) && enabled,
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job || !ACTIVE_IMPORT_STATUSES.has(job.status)) {
        return false;
      }

      if (job.status === "queued") {
        const queuedForMs = Date.now() - new Date(job.created_at).getTime();
        return queuedForMs > QUEUED_JOB_POLL_TIMEOUT_MS ? false : 1500;
      }

      const heartbeatAt = job.heartbeat_at ?? job.started_at ?? job.created_at;
      const heartbeatAgeMs = Date.now() - new Date(heartbeatAt).getTime();
      if (heartbeatAgeMs > RUNNING_JOB_HEARTBEAT_TIMEOUT_MS) {
        return false;
      }

      return 2500;
    },
  });
}

export function useCreateImportJobMutation() {
  return useMutation({
    mutationFn: (payload: SessionImportRequestDto) => createImportJob(payload),
  });
}
