import { PageContainer } from "../app/layout/PageContanier";
import type { HealthStatus } from "../data/mappers/health.mapper";
import { normalizeHealthStatus } from "../data/mappers/health.mapper";
import {
  useApiHealthQuery,
  useRootHealthQuery,
} from "../data/queries/health.queries";
import { useAuthHealthQuery } from "../data/queries/auth.queries";
import {
  useFeatureMetricsHealthQuery,
  useIngestionHealthQuery,
  useNormalizationHealthQuery,
  useStoryFeedHealthQuery,
} from "../data/queries/module-health.queries";
import { useImportJobsQuery } from "../data/queries/session-import.queries";
import { useSessionsQuery } from "../data/queries/sessions.queries";
import { useTelemetryMaterializationJobsQuery } from "../data/queries/telemetry-materialization.queries";
import "./system-health-page.css";

type HealthFact = {
  label: string;
  value: string;
};

type SummaryTileProps = {
  label: string;
  value: string;
  description: string;
  status: HealthStatus;
};

type DomainCardProps = {
  eyebrow: string;
  title: string;
  description: string;
  status: HealthStatus;
  facts: HealthFact[];
  endpoints?: string[];
  note: string;
};

function getStatusLabel(status: HealthStatus): string {
  switch (status) {
    case "healthy":
      return "Healthy";
    case "degraded":
      return "Needs attention";
    case "down":
      return "Unavailable";
    default:
      return "Checking";
  }
}

function combineStatuses(statuses: HealthStatus[]): HealthStatus {
  if (statuses.some((status) => status === "down")) {
    return "down";
  }

  if (statuses.some((status) => status === "degraded")) {
    return "degraded";
  }

  if (statuses.every((status) => status === "healthy")) {
    return "healthy";
  }

  if (statuses.some((status) => status === "healthy")) {
    return "degraded";
  }

  return "unknown";
}

function formatBoolean(value: boolean | null | undefined, labels?: {
  trueLabel: string;
  falseLabel: string;
}): string {
  if (value === true) {
    return labels?.trueLabel ?? "Yes";
  }

  if (value === false) {
    return labels?.falseLabel ?? "No";
  }

  return "Unknown";
}

function formatCount(value: number | null | undefined): string {
  return typeof value === "number" ? value.toLocaleString() : "Unknown";
}

function formatBytes(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "Unknown";
  }

  if (value < 1024) {
    return `${value.toLocaleString()} B`;
  }

  const units = ["KB", "MB", "GB"];
  let size = value / 1024;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

function SummaryTile({ label, value, description, status }: SummaryTileProps) {
  return (
    <article className="surface-card system-health-summary-tile">
      <div className="system-health-summary-tile__header">
        <span className="system-health-summary-tile__label">{label}</span>
        <span className={`system-health-badge system-health-badge--${status}`}>
          {getStatusLabel(status)}
        </span>
      </div>

      <strong className="system-health-summary-tile__value">{value}</strong>
      <p className="system-health-summary-tile__description">{description}</p>
    </article>
  );
}

function DomainCard({
  eyebrow,
  title,
  description,
  status,
  facts,
  endpoints = [],
  note,
}: DomainCardProps) {
  return (
    <article className="surface-card system-health-card">
      <header className="system-health-card__header">
        <div>
          <p className="system-health-card__eyebrow">{eyebrow}</p>
          <h2 className="system-health-card__title">{title}</h2>
        </div>

        <span className={`system-health-badge system-health-badge--${status}`}>
          {getStatusLabel(status)}
        </span>
      </header>

      <p className="system-health-card__description">{description}</p>

      <dl className="system-health-card__facts">
        {facts.map((fact) => (
          <div key={`${title}-${fact.label}`} className="system-health-card__fact">
            <dt className="system-health-card__fact-label">{fact.label}</dt>
            <dd className="system-health-card__fact-value">{fact.value}</dd>
          </div>
        ))}
      </dl>

      {endpoints.length > 0 ? (
        <div className="system-health-card__endpoints">
          {endpoints.map((endpoint) => (
            <span key={endpoint} className="system-health-chip">
              {endpoint}
            </span>
          ))}
        </div>
      ) : null}

      <p className="system-health-card__note">{note}</p>
    </article>
  );
}

export function SystemHealthPage() {
  const rootHealth = useRootHealthQuery();
  const apiHealth = useApiHealthQuery();
  const authHealth = useAuthHealthQuery();
  const sessionsQuery = useSessionsQuery();
  const importJobsQuery = useImportJobsQuery(25);
  const telemetryJobsQuery = useTelemetryMaterializationJobsQuery(25);
  const ingestionHealth = useIngestionHealthQuery();
  const normalizationHealth = useNormalizationHealthQuery();
  const featureMetricsHealth = useFeatureMetricsHealthQuery();
  const storyFeedHealth = useStoryFeedHealthQuery();

  const backendStatus = normalizeHealthStatus(rootHealth.data);
  const apiStatus = normalizeHealthStatus(apiHealth.data);
  const databaseStatus = normalizeHealthStatus(apiHealth.data?.db);
  const authStatus = normalizeHealthStatus(authHealth.data);

  const sessionsStatus = sessionsQuery.isError
    ? "down"
    : sessionsQuery.isSuccess
      ? "healthy"
      : "unknown";

  const importJobs = importJobsQuery.data?.jobs ?? [];
  const queuedJobs = importJobs.filter((job) => job.status === "queued");
  const runningJobs = importJobs.filter((job) => job.status === "running");
  const failedJobs = importJobs.filter((job) => job.status === "failed");
  const completedJobs = importJobs.filter((job) => job.status === "completed");
  const latestJob = importJobs[0] ?? null;
  const telemetryJobs = telemetryJobsQuery.data?.jobs ?? [];
  const queuedTelemetryJobs = telemetryJobs.filter((job) => job.status === "queued");
  const runningTelemetryJobs = telemetryJobs.filter((job) => job.status === "running");
  const failedTelemetryJobs = telemetryJobs.filter((job) => job.status === "failed");
  const completedTelemetryJobs = telemetryJobs.filter((job) => job.status === "completed");
  const latestTelemetryJob = telemetryJobs[0] ?? null;

  const importJobsStatus = importJobsQuery.isError
    ? "down"
    : importJobsQuery.isSuccess
      ? queuedJobs.length > 0 && runningJobs.length === 0
        ? "degraded"
        : "healthy"
      : "unknown";
  const telemetryJobsStatus = telemetryJobsQuery.isError
    ? "down"
    : telemetryJobsQuery.isSuccess
      ? queuedTelemetryJobs.length > 0 && runningTelemetryJobs.length === 0
        ? "degraded"
        : "healthy"
      : "unknown";

  const ingestionStatus = ingestionHealth.data?.details?.configured
    ? "healthy"
    : ingestionHealth.isError
      ? "down"
      : normalizeHealthStatus(ingestionHealth.data);

  const normalizationStatus = normalizationHealth.data?.details?.canonical_schema_ready
    ? "healthy"
    : normalizationHealth.isError
      ? "down"
      : normalizeHealthStatus(normalizationHealth.data?.details ?? normalizationHealth.data);

  const featureMetricsStatus = featureMetricsHealth.isError
    ? "down"
    : normalizeHealthStatus(featureMetricsHealth.data?.details ?? featureMetricsHealth.data);

  const storyFeedStatus = storyFeedHealth.isError
    ? "down"
    : storyFeedHealth.data?.details?.enabled
      ? "healthy"
      : normalizeHealthStatus(storyFeedHealth.data?.details ?? storyFeedHealth.data);

  const pipelineStatus = combineStatuses([
    importJobsStatus,
    telemetryJobsStatus,
    sessionsStatus,
    ingestionStatus,
    normalizationStatus,
  ]);

  const platformStatus = combineStatuses([
    backendStatus,
    apiStatus,
    databaseStatus,
    authStatus,
  ]);

  const futureModulesStatus = combineStatuses([
    featureMetricsStatus,
    storyFeedStatus,
  ]);

  const cachedSessions = sessionsQuery.data?.length ?? 0;
  const coreSessions = sessionsQuery.data?.filter((session) => session.import_profile === "core").length ?? 0;
  const fullSessions = sessionsQuery.data?.filter((session) => session.import_profile === "full").length ?? 0;
  const telemetryLoadedSessions =
    sessionsQuery.data?.filter((session) => session.telemetry_status === "loaded").length ?? 0;
  const workerSignal = runningJobs.length > 0
    ? `${runningJobs.length} running`
    : queuedJobs.length > 0
      ? "Queued work waiting"
      : importJobsQuery.isSuccess
        ? "Idle or no recent jobs"
        : "Checking";
  const telemetryWorkerSignal = runningTelemetryJobs.length > 0
    ? `${runningTelemetryJobs.length} running`
    : queuedTelemetryJobs.length > 0
      ? "Queued slices waiting"
      : telemetryJobsQuery.isSuccess
        ? "Idle or cached"
        : "Checking";

  return (
    <PageContainer>
      <div className="system-health-page">
        <section className="system-health-hero">
          <div className="system-health-hero__copy">
            <span className="ui-pill ui-pill--ready">Diagnostics</span>
            <h1 className="display-font system-health-hero__title">System Health</h1>
            <p className="system-health-hero__lead">
              This page follows the current import architecture: clients create import jobs,
              the worker loads FastF1 through profile-aware ingestion, normalization builds
              the canonical snapshot, and PostgreSQL remains the selected-session cache.
            </p>
          </div>

          <div className="system-health-flow">
            <div className="system-health-flow__step">
              <span className="system-health-flow__label">Source</span>
              <strong>FastF1</strong>
            </div>
            <div className="system-health-flow__arrow">-&gt;</div>
            <div className="system-health-flow__step">
              <span className="system-health-flow__label">Queue</span>
              <strong>Import jobs</strong>
            </div>
            <div className="system-health-flow__arrow">-&gt;</div>
            <div className="system-health-flow__step">
              <span className="system-health-flow__label">Worker</span>
              <strong>Profile load</strong>
            </div>
            <div className="system-health-flow__arrow">-&gt;</div>
            <div className="system-health-flow__step">
              <span className="system-health-flow__label">Shape</span>
              <strong>Normalization</strong>
            </div>
            <div className="system-health-flow__arrow">-&gt;</div>
            <div className="system-health-flow__step">
              <span className="system-health-flow__label">Serve</span>
              <strong>Sessions</strong>
            </div>
          </div>
        </section>

        <section className="system-health-summary">
          <SummaryTile
            label="Session pipeline"
            value={getStatusLabel(pipelineStatus)}
            description="Import jobs, source loading, normalization, and session-cache reads."
            status={pipelineStatus}
          />

          <SummaryTile
            label="Import queue"
            value={workerSignal}
            description={`${formatCount(queuedJobs.length)} queued, ${formatCount(runningJobs.length)} running, ${formatCount(failedJobs.length)} failed in the recent job window.`}
            status={importJobsStatus}
          />

          <SummaryTile
            label="Telemetry cache"
            value={telemetryWorkerSignal}
            description={`${formatCount(queuedTelemetryJobs.length)} queued, ${formatCount(runningTelemetryJobs.length)} running, ${formatCount(completedTelemetryJobs.length)} completed telemetry slice jobs.`}
            status={telemetryJobsStatus}
          />

          <SummaryTile
            label="Cached sessions"
            value={formatCount(cachedSessions)}
            description={`${formatCount(fullSessions)} full imports, ${formatCount(coreSessions)} core imports, ${formatCount(telemetryLoadedSessions)} with telemetry loaded.`}
            status={sessionsStatus}
          />

          <SummaryTile
            label="Database link"
            value={apiHealth.data?.db?.driver ?? "Unknown"}
            description={
              apiHealth.isLoading
                ? "Database connectivity check is still running."
                : apiHealth.data?.db?.status === "connected"
                ? "Delivery API can reach the relational store."
                : "Database connectivity still needs attention."
            }
            status={databaseStatus}
          />

          <SummaryTile
            label="Platform"
            value={getStatusLabel(platformStatus)}
            description="Backend root, delivery API, database connectivity, and auth endpoint reachability."
            status={platformStatus}
          />
        </section>

        <section className="system-health-section">
          <div className="system-health-section__header">
            <div>
              <p className="system-health-section__eyebrow">Core domains</p>
              <h2 className="system-health-section__title">Import and session-cache pipeline</h2>
            </div>
            <p className="system-health-section__body">
              These domains now split slow import work away from normal reads. Import jobs
              track operational state, ingestion loads the selected profile, normalization
              produces the canonical shape, and the session domain serves cached data.
            </p>
          </div>

          <div className="system-health-grid">
            <DomainCard
              eyebrow="Session import"
              title="Job queue and worker path"
              description="Owns background import requests, progress stages, heartbeat recovery, retries, and the handoff into canonical session storage."
              status={importJobsStatus}
              facts={[
                {
                  label: "Route reachability",
                  value: importJobsQuery.isError ? "Unavailable" : importJobsQuery.isSuccess ? "Reachable" : "Checking",
                },
                {
                  label: "Queued jobs",
                  value: formatCount(queuedJobs.length),
                },
                {
                  label: "Running jobs",
                  value: formatCount(runningJobs.length),
                },
                {
                  label: "Latest stage",
                  value: latestJob?.progress_stage ?? "No recent jobs",
                },
                {
                  label: "Completed recent",
                  value: formatCount(completedJobs.length),
                },
              ]}
              endpoints={[
                "/api/session-import/jobs",
                "/api/session-import/jobs/{id}",
                "python -m app.worker",
              ]}
              note={
                queuedJobs.length > 0 && runningJobs.length === 0
                  ? "Queued jobs are waiting with no running job in the recent window. If this persists, check the worker process."
                  : "This endpoint proves the queue API is reachable. Worker liveness is inferred from running jobs and queue movement."
              }
            />

            <DomainCard
              eyebrow="Session domain"
              title="Selected-session cache"
              description="Owns canonical session persistence, cache lifecycle, entry reads, telemetry reads, and replay-oriented tick access."
              status={sessionsStatus}
              facts={[
                {
                  label: "Route reachability",
                  value: sessionsQuery.isError ? "Unavailable" : sessionsQuery.isSuccess ? "Reachable" : "Checking",
                },
                {
                  label: "Cached sessions",
                  value: formatCount(cachedSessions),
                },
                {
                  label: "Full imports",
                  value: formatCount(fullSessions),
                },
                {
                  label: "Core imports",
                  value: formatCount(coreSessions),
                },
                {
                  label: "Telemetry loaded",
                  value: formatCount(telemetryLoadedSessions),
                },
              ]}
              endpoints={[
                "/api/sessions",
                "/api/sessions/catalog",
                "/api/sessions/import",
                "/api/sessions/{id}/entries",
                "/api/sessions/{id}/ticks",
              ]}
              note={
                sessionsQuery.isError
                  ? "The sessions API is not responding cleanly right now, so archive and detail screens would be blocked."
                  : "This is still the stable frontend read surface. Import jobs feed this cache; widgets read from it."
              }
            />

            <DomainCard
              eyebrow="Telemetry materialization"
              title="On-demand telemetry slices"
              description="Owns reusable telemetry cache segments for selected entries, scopes, and modes without creating separate sessions."
              status={telemetryJobsStatus}
              facts={[
                {
                  label: "Route reachability",
                  value: telemetryJobsQuery.isError ? "Unavailable" : telemetryJobsQuery.isSuccess ? "Reachable" : "Checking",
                },
                {
                  label: "Queued slice jobs",
                  value: formatCount(queuedTelemetryJobs.length),
                },
                {
                  label: "Running slice jobs",
                  value: formatCount(runningTelemetryJobs.length),
                },
                {
                  label: "Failed slice jobs",
                  value: formatCount(failedTelemetryJobs.length),
                },
                {
                  label: "Latest stage",
                  value: latestTelemetryJob?.progress_stage ?? "No recent jobs",
                },
              ]}
              endpoints={[
                "/api/telemetry/materialization/ensure",
                "/api/telemetry/materialization/jobs/{id}",
                "python -m app.worker",
              ]}
              note="Lookback and simulation both use these segments. Loading one driver/lap adds to the session cache; it does not replace or delete other cached slices."
            />

            <DomainCard
              eyebrow="Ingestion domain"
              title="FastF1 source loader"
              description="Handles source access, season catalog discovery, selected-session loading, and extraction of source-shaped records from FastF1."
              status={ingestionStatus}
              facts={[
                {
                  label: "Source",
                  value: ingestionHealth.data?.details?.source_name ?? "Unknown",
                },
                {
                  label: "Configured",
                  value: formatBoolean(ingestionHealth.data?.details?.configured, {
                    trueLabel: "Yes",
                    falseLabel: "No",
                  }),
                },
                {
                  label: "Adapter state",
                  value: ingestionHealth.data?.details?.status ?? "Checking",
                },
                {
                  label: "Import timeout",
                  value:
                    typeof ingestionHealth.data?.details?.import_timeout_seconds === "number"
                      ? `${ingestionHealth.data.details.import_timeout_seconds}s`
                      : "Unknown",
                },
                {
                  label: "FastF1 cache size",
                  value: formatBytes(ingestionHealth.data?.details?.cache_size_bytes),
                },
                {
                  label: "Profiles",
                  value: "core, full",
                },
              ]}
              endpoints={["/api/ingestion/health", "/api/sessions/catalog", "/api/session-import/jobs"]}
              note={
                ingestionHealth.data?.details?.cache_dir
                  ? `FastF1 cache directory is configured at ${ingestionHealth.data.details.cache_dir}.`
                  : "FastF1 cache directory is not available in the current response."
              }
            />

            <DomainCard
              eyebrow="Normalization domain"
              title="Canonical snapshot builder"
              description="Transforms source bundles into the internal session snapshot, including entries, laps, stints, telemetry linkages, and aligned session ticks."
              status={normalizationStatus}
              facts={[
                {
                  label: "Pipeline",
                  value: normalizationHealth.data?.details?.pipeline_name ?? "Unknown",
                },
                {
                  label: "Schema readiness",
                  value: formatBoolean(normalizationHealth.data?.details?.canonical_schema_ready, {
                    trueLabel: "Ready",
                    falseLabel: "Not ready",
                  }),
                },
                {
                  label: "Pipeline state",
                  value: normalizationHealth.data?.details?.status ?? "Checking",
                },
                {
                  label: "Output shape",
                  value: "Entry-centric canonical snapshot",
                },
                {
                  label: "Builder selection",
                  value: "By source",
                },
              ]}
              endpoints={["/api/normalization/health", "/api/session-import/jobs"]}
              note="Normalization now records whether the snapshot came from a core or full import while keeping FastF1-specific source shapes out of storage."
            />
          </div>
        </section>

        <section className="system-health-section">
          <div className="system-health-section__header">
            <div>
              <p className="system-health-section__eyebrow">Supporting services</p>
              <h2 className="system-health-section__title">Infrastructure around the pipeline</h2>
            </div>
            <p className="system-health-section__body">
              These services matter, but they are supporting layers around the main session
              flow rather than the center of the archive/import experience.
            </p>
          </div>

          <div className="system-health-grid system-health-grid--secondary">
            <DomainCard
              eyebrow="Platform"
              title="Backend delivery surface"
              description="Root backend health, delivery API reachability, database connectivity, and auth route availability."
              status={platformStatus}
              facts={[
                {
                  label: "Backend service",
                  value: rootHealth.data?.service ?? "Unknown",
                },
                {
                  label: "API service",
                  value: apiHealth.data?.service ?? "Unknown",
                },
                {
                  label: "Database state",
                  value: apiHealth.data?.db?.status ?? "Unknown",
                },
                {
                  label: "Auth route",
                  value: authHealth.isLoading
                    ? "Checking"
                    : authHealth.isError
                      ? "Unavailable"
                      : "Reachable",
                },
              ]}
              endpoints={["/health", "/api/health", "/api/auth/health"]}
              note={
                apiHealth.data?.db?.error
                  ? `Database error: ${apiHealth.data.db.error}`
                  : "If this card is unhealthy, module-level health is less trustworthy because the delivery layer itself is unstable."
              }
            />

            <DomainCard
              eyebrow="Future domains"
              title="Feature metrics and story feed"
              description="These domains exist in the architecture, but they are not on the critical path for importing and serving session cache data yet."
              status={futureModulesStatus}
              facts={[
                {
                  label: "Feature metrics",
                  value: featureMetricsHealth.data?.details?.status ?? "Unknown",
                },
                {
                  label: "Computed fields",
                  value: formatCount(featureMetricsHealth.data?.details?.computed_fields_available),
                },
                {
                  label: "Story feed",
                  value: storyFeedHealth.data?.details?.status ?? "Unknown",
                },
                {
                  label: "Story feed enabled",
                  value: formatBoolean(storyFeedHealth.data?.details?.enabled, {
                    trueLabel: "Enabled",
                    falseLabel: "Disabled",
                  }),
                },
              ]}
              endpoints={["/api/feature-metrics/health", "/api/story-feed/health"]}
              note="It is normal for these cards to be degraded right now because they are scaffolded domains rather than active product surfaces."
            />
          </div>
        </section>
      </div>
    </PageContainer>
  );
}
