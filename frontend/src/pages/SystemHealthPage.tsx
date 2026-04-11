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
import { PageContainer } from "../app/layout/PageContanier";

type HealthCardProps = {
  title: string;
  isLoading: boolean;
  isError: boolean;
  data?: unknown;
};

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "Could not serialize response data.";
  }
}

function HealthCard({ title, isLoading, isError, data }: HealthCardProps) {
  return (
    <section className="surface-card rounded-[18px] p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-white">{title}</h2>

        {isLoading && (
          <span className="rounded-full border border-[var(--color-border-subtle)] px-3 py-1 text-xs text-[var(--color-text-secondary)]">
            Loading
          </span>
        )}

        {!isLoading && isError && (
          <span className="rounded-full border border-[rgba(220,38,38,0.38)] bg-[rgba(220,38,38,0.12)] px-3 py-1 text-xs text-red-200">
            Error
          </span>
        )}

        {!isLoading && !isError && (
          <span className="rounded-full border border-[rgba(22,199,132,0.35)] bg-[rgba(22,199,132,0.14)] px-3 py-1 text-xs text-[var(--color-success)]">
            OK
          </span>
        )}
      </div>

      <div className="mt-4">
        {isLoading && <p className="text-sm text-neutral-400">Fetching health data...</p>}

        {isError && (
          <p className="text-sm text-red-400">
            Failed to load this health endpoint.
          </p>
        )}

        {!isLoading && !isError && data !== undefined && (
          <pre className="overflow-auto rounded-2xl border border-[var(--color-border-subtle)] bg-black/20 p-3 text-sm text-neutral-200">
            {formatJson(data)}
          </pre>
        )}
      </div>
    </section>
  );
}

export function SystemHealthPage() {
  const rootHealth = useRootHealthQuery();
  const apiHealth = useApiHealthQuery();
  const authHealth = useAuthHealthQuery();
  const ingestionHealth = useIngestionHealthQuery();
  const normalizationHealth = useNormalizationHealthQuery();
  const featureMetricsHealth = useFeatureMetricsHealthQuery();
  const storyFeedHealth = useStoryFeedHealthQuery();

  return (
    <PageContainer>
      <div className="space-y-6">
        <div>
          <span className="ui-pill ui-pill--ready">Diagnostics</span>
          <h1 className="display-font mt-4 text-[2rem] leading-none text-white">
            System Health
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--color-text-secondary)]">
            Internal diagnostics page for backend and module health endpoints.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <HealthCard
            title="Root Health"
            isLoading={rootHealth.isLoading}
            isError={rootHealth.isError}
            data={rootHealth.data}
          />

          <HealthCard
            title="API Health"
            isLoading={apiHealth.isLoading}
            isError={apiHealth.isError}
            data={apiHealth.data}
          />

          <HealthCard
            title="Auth Health"
            isLoading={authHealth.isLoading}
            isError={authHealth.isError}
            data={authHealth.data}
          />

          <HealthCard
            title="Ingestion Health"
            isLoading={ingestionHealth.isLoading}
            isError={ingestionHealth.isError}
            data={ingestionHealth.data}
          />

          <HealthCard
            title="Normalization Health"
            isLoading={normalizationHealth.isLoading}
            isError={normalizationHealth.isError}
            data={normalizationHealth.data}
          />

          <HealthCard
            title="Feature Metrics Health"
            isLoading={featureMetricsHealth.isLoading}
            isError={featureMetricsHealth.isError}
            data={featureMetricsHealth.data}
          />

          <HealthCard
            title="Story Feed Health"
            isLoading={storyFeedHealth.isLoading}
            isError={storyFeedHealth.isError}
            data={storyFeedHealth.data}
          />
        </div>
      </div>
    </PageContainer>
  );
}
