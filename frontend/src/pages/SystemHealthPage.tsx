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
    <section className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-white">{title}</h2>

        {isLoading && (
          <span className="rounded-md border border-neutral-700 px-2 py-1 text-xs text-neutral-300">
            Loading
          </span>
        )}

        {!isLoading && isError && (
          <span className="rounded-md border border-red-900 bg-red-950/50 px-2 py-1 text-xs text-red-300">
            Error
          </span>
        )}

        {!isLoading && !isError && (
          <span className="rounded-md border border-emerald-900 bg-emerald-950/50 px-2 py-1 text-xs text-emerald-300">
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
          <pre className="overflow-auto rounded-lg bg-black/30 p-3 text-sm text-neutral-200">
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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">System Health</h1>
        <p className="mt-1 text-sm text-neutral-400">
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
  );
}