import type { SessionTelemetryStatus } from "../../data/contracts/sessions.contracts";
import type {
  ImportJobStage,
  ImportJobStatus,
} from "../../data/contracts/session-import.contracts";
import type { TelemetryMaterializationJobDto } from "../../data/contracts/telemetry-materialization.contracts";

export function getTelemetryWarmupTitle(
  telemetryStatus: SessionTelemetryStatus,
  jobStatus?: ImportJobStatus,
  jobStage?: ImportJobStage,
) {
  if (jobStatus === "failed") {
    return "Telemetry warmup failed";
  }

  if (jobStatus === "queued") {
    return "Telemetry job is queued";
  }

  if (jobStatus === "running") {
    switch (jobStage) {
      case "loading_source":
        return "Loading full telemetry";
      case "normalizing":
        return "Normalizing full telemetry";
      case "persisting":
        return "Writing telemetry cache";
      default:
        return "Preparing full telemetry";
    }
  }

  if (telemetryStatus === "partial") {
    return "Telemetry is partially available";
  }

  if (telemetryStatus === "unavailable") {
    return "Telemetry is unavailable";
  }

  return "Workspace opened on core data";
}

export function getTelemetryWarmupDescription(
  telemetryStatus: SessionTelemetryStatus,
  jobStatus?: ImportJobStatus,
  jobStage?: ImportJobStage,
  errorMessage?: string | null,
) {
  if (jobStatus === "failed") {
    return (
      errorMessage ??
      "The session is still open on core data, but the background full telemetry import failed."
    );
  }

  if (jobStatus === "queued") {
    return "The session is usable now. Full car and position telemetry will appear after the worker claims this job.";
  }

  if (jobStatus === "running") {
    if (jobStage === "persisting") {
      return "The session stays open while the worker replaces the core cache with the full telemetry cache using the same session id.";
    }
    return "You can inspect entries, laps, events, and layouts while the worker fills the heavier telemetry cache.";
  }

  if (telemetryStatus === "partial") {
    return "The data source returned only part of the requested telemetry. Some widgets may have less data than expected.";
  }

  if (telemetryStatus === "unavailable") {
    return "The data source could not provide full telemetry for this session. Laps, entries, events, and timing context remain available.";
  }

  return "The lightweight core profile is cached. Full telemetry has not been requested or is not being tracked in this browser.";
}

export function getWarmupPercent(stage?: ImportJobStage) {
  switch (stage) {
    case "queued":
      return 12;
    case "loading_source":
      return 42;
    case "normalizing":
      return 68;
    case "persisting":
      return 88;
    case "completed":
      return 100;
    default:
      return 20;
  }
}

export function isActiveTelemetryJob(job: TelemetryMaterializationJobDto) {
  return job.status === "queued" || job.status === "running";
}

export function compareTelemetryJobsByActivity(
  left: TelemetryMaterializationJobDto,
  right: TelemetryMaterializationJobDto,
) {
  const leftActive = isActiveTelemetryJob(left);
  const rightActive = isActiveTelemetryJob(right);

  if (leftActive !== rightActive) {
    return leftActive ? -1 : 1;
  }

  return (
    new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
  );
}

export function getTelemetryMaterializationTitle(
  jobs: TelemetryMaterializationJobDto[],
) {
  if (jobs.length === 1) {
    return `${formatTelemetryJobSummary(jobs[0])} is being prepared`;
  }

  return `${jobs.length} telemetry cache requests are being prepared`;
}

export function getTelemetryMaterializationDescription(
  jobs: TelemetryMaterializationJobDto[],
) {
  const summaries = jobs
    .slice(0, 3)
    .map(
      (job) =>
        `${formatTelemetryJobSummary(job)}: ${getTelemetryMaterializationStageLabel(job)}`,
    );
  const suffix =
    jobs.length > summaries.length
      ? `, plus ${jobs.length - summaries.length} more`
      : "";
  return `${summaries.join("; ")}${suffix}. Widgets will read the normal telemetry API as soon as these cache segments are ready.`;
}

export function getTelemetryMaterializationDoneTitle(
  job: TelemetryMaterializationJobDto,
) {
  if (job.status === "failed") {
    return `${formatTelemetryJobSummary(job)} failed`;
  }

  if (job.status === "completed") {
    return `${formatTelemetryJobSummary(job)} is cached`;
  }

  return "Telemetry cache activity";
}

export function getTelemetryMaterializationDoneDescription(
  job: TelemetryMaterializationJobDto,
) {
  if (job.status === "failed") {
    return (
      job.error_message ??
      "The worker could not prepare this telemetry cache segment."
    );
  }

  if (job.status === "completed") {
    return `The worker completed this ${job.scope}-scope cache request. If a widget still looks empty, it is now reading sample rows rather than waiting on The data source.`;
  }

  return "Telemetry cache status is being refreshed.";
}

export function formatTelemetryJobSummary(job: TelemetryMaterializationJobDto) {
  const kindLabel = job.kinds
    .map((kind) => (kind === "car" ? "car" : "position"))
    .join(" + ");
  const scopeLabel =
    job.scope === "lap" && job.lap_number != null
      ? `lap ${job.lap_number}`
      : "session";
  return `${capitalize(kindLabel)} telemetry, ${scopeLabel}`;
}

export function getTelemetryMaterializationStageLabel(
  job: TelemetryMaterializationJobDto,
) {
  if (job.status === "queued") {
    return "Queued for worker";
  }

  if (job.status === "completed") {
    return "Completed";
  }

  if (job.status === "failed") {
    return "Failed";
  }

  switch (job.progress_stage) {
    case "loading_source":
      return "Loading The data source source data";
    case "normalizing":
      return "Normalizing telemetry rows";
    case "persisting":
      return "Writing cache rows";
    default:
      return "Preparing telemetry";
  }
}

export function getMaterializationPercent(stage?: string) {
  switch (stage) {
    case "queued":
      return 15;
    case "loading_source":
      return 42;
    case "normalizing":
      return 68;
    case "persisting":
      return 88;
    case "completed":
      return 100;
    default:
      return 24;
  }
}

export function formatRowsWritten(rowsWritten: number | null) {
  if (rowsWritten == null || rowsWritten <= 0) {
    return "";
  }

  return ` - ${rowsWritten.toLocaleString()} rows`;
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function getTelemetryStatusLabel(status: SessionTelemetryStatus) {
  switch (status) {
    case "loaded":
      return "Loaded";
    case "partial":
      return "Partial";
    case "unavailable":
      return "Unavailable";
    case "not_loaded":
    default:
      return "Lazy";
  }
}
