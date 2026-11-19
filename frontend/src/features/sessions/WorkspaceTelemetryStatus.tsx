import type { SessionTelemetryStatus } from "../../data/contracts/sessions.contracts";
import type {
  ImportJobStage,
  ImportJobStatus,
} from "../../data/contracts/session-import.contracts";
import type { TelemetryMaterializationJobDto } from "../../data/contracts/telemetry-materialization.contracts";

import {
  getTelemetryWarmupTitle,
  isActiveTelemetryJob,
  formatTelemetryJobSummary,
  getTelemetryWarmupDescription,
  getWarmupPercent,
  getTelemetryMaterializationTitle,
  getTelemetryMaterializationDescription,
  getTelemetryMaterializationDoneTitle,
  getTelemetryMaterializationDoneDescription,
  getTelemetryMaterializationStageLabel,
  getMaterializationPercent,
  formatRowsWritten,
} from "./telemetry-status";

export type WorkspaceStatusItem = {
  label: string;
  value: string;
  detail: string;
  tone: "ready" | "loading" | "warning" | "idle";
};

export function TelemetryWarmupBanner({
  telemetryStatus,
  jobStatus,
  jobStage,
  errorMessage,
  materializationJobs,
  materializationLoading,
}: {
  telemetryStatus: SessionTelemetryStatus;
  jobStatus?: ImportJobStatus;
  jobStage?: ImportJobStage;
  errorMessage?: string | null;
  materializationJobs: TelemetryMaterializationJobDto[];
  materializationLoading: boolean;
}) {
  const activeMaterializationJobs =
    materializationJobs.filter(isActiveTelemetryJob);
  const latestMaterializationJob = materializationJobs[0];
  const failedMaterializationJob = materializationJobs.find(
    (job) => job.status === "failed",
  );

  if (telemetryStatus === "loaded" && materializationJobs.length === 0) {
    return null;
  }

  const jobActive = jobStatus === "queued" || jobStatus === "running";
  const materializationActive = activeMaterializationJobs.length > 0;
  const isError =
    telemetryStatus === "unavailable" ||
    jobStatus === "failed" ||
    Boolean(failedMaterializationJob);
  const title = materializationActive
    ? getTelemetryMaterializationTitle(activeMaterializationJobs)
    : latestMaterializationJob
      ? getTelemetryMaterializationDoneTitle(latestMaterializationJob)
      : getTelemetryWarmupTitle(telemetryStatus, jobStatus, jobStage);
  const description = materializationActive
    ? getTelemetryMaterializationDescription(activeMaterializationJobs)
    : latestMaterializationJob
      ? getTelemetryMaterializationDoneDescription(latestMaterializationJob)
      : getTelemetryWarmupDescription(
          telemetryStatus,
          jobStatus,
          jobStage,
          errorMessage,
        );
  const jobsToShow = materializationActive
    ? activeMaterializationJobs
    : materializationJobs
        .filter((job) => job.status === "completed" || job.status === "failed")
        .slice(0, 3);

  return (
    <div
      className={`sessions-telemetry-banner${isError ? " sessions-telemetry-banner--warning" : ""}`}
    >
      <div>
        <span
          className={`ui-pill ${jobActive || materializationActive ? "ui-pill--live" : "ui-pill--focus"}`}
        >
          {materializationActive
            ? "Telemetry cache"
            : jobActive
              ? "Warming telemetry"
              : "Telemetry"}
        </span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {jobsToShow.length > 0 || materializationLoading ? (
        <div className="sessions-telemetry-banner__jobs">
          {jobsToShow.map((job) => (
            <div
              key={job.id}
              className={`sessions-telemetry-job sessions-telemetry-job--${job.status}`}
            >
              <strong>{formatTelemetryJobSummary(job)}</strong>
              <span>{getTelemetryMaterializationStageLabel(job)}</span>
              <small>
                {job.entry_ids.length}{" "}
                {job.entry_ids.length === 1 ? "entry" : "entries"}
                {formatRowsWritten(job.rows_written)}
              </small>
            </div>
          ))}
          {materializationLoading ? (
            <span className="sessions-inline-loading">
              Refreshing worker status...
            </span>
          ) : null}
        </div>
      ) : null}
      {jobActive || materializationActive ? (
        <div className="sessions-telemetry-banner__meter" aria-hidden="true">
          <span
            style={{
              width: `${materializationActive ? getMaterializationPercent(activeMaterializationJobs[0]?.progress_stage) : getWarmupPercent(jobStage)}%`,
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

export function WorkspaceStatusStrip({
  items,
}: {
  items: WorkspaceStatusItem[];
}) {
  return (
    <div
      className="sessions-status-strip"
      aria-label="Workspace loading status"
    >
      {items.map((item) => (
        <div
          key={item.label}
          className={`sessions-status-item sessions-status-item--${item.tone}`}
        >
          <span className="sessions-status-item__dot" aria-hidden="true" />
          <div>
            <span className="sessions-status-item__label">{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.detail}</small>
          </div>
        </div>
      ))}
    </div>
  );
}
