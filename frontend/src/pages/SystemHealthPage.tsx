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
import { useSessionsQuery } from "../data/queries/sessions.queries";
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

  return (
    <PageContainer>
      <div className="system-health-page">
        <section className="system-health-hero">
          <div className="system-health-hero__copy">
            <span className="ui-pill ui-pill--ready">Diagnostics</span>
            <h1 className="display-font system-health-hero__title">System Health</h1>
            <p className="system-health-hero__lead">
              This page is centered on the current session pipeline the frontend will depend
              on most: FastF1 source access, ingestion, normalization, and the selected-session
              cache exposed through the sessions API.
            </p>
          </div>

          <div className="system-health-flow">
            <div className="system-health-flow__step">
              <span className="system-health-flow__label">Source</span>
              <strong>FastF1</strong>
            </div>
            <div className="system-health-flow__arrow">-&gt;</div>
            <div className="system-health-flow__step">
              <span className="system-health-flow__label">Load</span>
              <strong>Ingestion</strong>
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
            description="End-to-end import and cache path used by archive and telemetry surfaces."
            status={pipelineStatus}
          />

          <SummaryTile
            label="Cached sessions"
            value={formatCount(cachedSessions)}
            description="Sessions currently reachable through the selected-session cache."
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
              <h2 className="system-health-section__title">The session pipeline that matters to the frontend</h2>
            </div>
            <p className="system-health-section__body">
              These three domains work together. The sessions domain is the frontend-facing
              cache layer, ingestion loads source data, and normalization turns source rows
              into the canonical entry-centric model.
            </p>
          </div>

          <div className="system-health-grid">
            <DomainCard
              eyebrow="Session domain"
              title="Selected-session cache"
              description="Owns the archive-facing session model, session reads, entry reads, telemetry reads, and replay-oriented tick access."
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
                  label: "Role",
                  value: "Frontend-facing session and telemetry domain",
                },
                {
                  label: "Storage model",
                  value: "Selected-session cache",
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
                  : "This is the domain the frontend should treat as the stable read surface for imported sessions."
              }
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
              ]}
              endpoints={["/api/ingestion/health", "/api/sessions/catalog", "/api/sessions/import"]}
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
              ]}
              endpoints={["/api/normalization/health", "/api/sessions/import"]}
              note="Normalization is the layer that keeps FastF1-specific source shapes out of the session storage and query code."
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
