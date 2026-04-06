import { WidgetCard } from "../../shared/WidgetCard";
import { WidgetError, WidgetLoading } from "../../shared/WidgetState";

import { useApiHealthQuery } from "../../../data/queries/health.queries";
import { useAuthHealthQuery } from "../../../data/queries/auth.queries";
import {
  useIngestionHealthQuery,
  useNormalizationHealthQuery,
} from "../../../data/queries/module-health.queries";

import { mapHealthOverview } from "../../../data/mappers/health.mapper";

export function HealthOverviewWidget() {
  const api = useApiHealthQuery();
  const auth = useAuthHealthQuery();
  const ingestion = useIngestionHealthQuery();
  const normalization = useNormalizationHealthQuery();

  const isLoading =
    api.isLoading ||
    auth.isLoading ||
    ingestion.isLoading ||
    normalization.isLoading;

  const isError =
    api.isError ||
    auth.isError ||
    ingestion.isError ||
    normalization.isError;

  if (isLoading) {
    return (
      <WidgetCard title="System Health" description="Current platform status.">
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (isError) {
    return (
      <WidgetCard title="System Health" description="Current platform status.">
        <WidgetError />
      </WidgetCard>
    );
  }

  const model = mapHealthOverview({
    api: api.data,
    auth: auth.data,
    ingestion: ingestion.data,
    normalization: normalization.data,
  });

  return (
    <WidgetCard title="System Health" description="Current platform status.">
      <div className="metric-grid">
        {model.items.map((item) => (
          <div key={item.key} className="metric-tile">
            <span className="metric-tile__label">{item.label}</span>
            <strong className={`metric-tile__value status-${item.status}`}>
              {item.status}
            </strong>
          </div>
        ))}
      </div>
    </WidgetCard>
  );
}