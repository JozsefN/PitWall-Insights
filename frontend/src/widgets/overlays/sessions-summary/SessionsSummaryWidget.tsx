import { WidgetCard } from "../../shared/WidgetCard";
import { WidgetError, WidgetLoading } from "../../shared/WidgetState";

import { useSessionsQuery } from "../../../data/queries/sessions.queries";
import { mapSessionsSummary } from "../../../data/mappers/sessions.mapper";

export function SessionsSummaryWidget() {
  const { data, isLoading, isError } = useSessionsQuery();

  if (isLoading) {
    return (
      <WidgetCard title="Sessions" description="Recent session metrics.">
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (isError) {
    return (
      <WidgetCard title="Sessions" description="Recent session metrics.">
        <WidgetError />
      </WidgetCard>
    );
  }

  const model = mapSessionsSummary(data);

  return (
    <WidgetCard title="Sessions" description="Recent session metrics.">
      <div className="metric-grid">
        <div className="metric-tile">
          <span className="metric-tile__label">Total</span>
          <strong className="metric-tile__value">{model.total}</strong>
        </div>

        <div className="metric-tile">
          <span className="metric-tile__label">Active</span>
          <strong className="metric-tile__value">{model.active}</strong>
        </div>

        <div className="metric-tile">
          <span className="metric-tile__label">Failed</span>
          <strong className="metric-tile__value">{model.failed}</strong>
        </div>
      </div>
    </WidgetCard>
  );
}
