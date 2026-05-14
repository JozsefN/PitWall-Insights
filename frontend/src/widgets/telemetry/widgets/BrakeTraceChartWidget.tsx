import { useWorkspaceCarTelemetryResource } from "../../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import {
  buildBrakePoints,
  downsamplePoints,
  getEntryAccent,
  getEntryDisplayName,
} from "../../../features/sessions/session-utils";
import { WidgetCard } from "../../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../../shared/WidgetState";
import { SimpleLineChart } from "../components/SimpleLineChart";
import type { LineSeries, TelemetryWidgetOptions } from "../models";

export function BrakeTraceChartWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as TelemetryWidgetOptions;
  const workspace = useSessionWorkspace();
  const requiresLap = widgetOptions.requiresLap !== false;
  const canRequestTelemetry = workspace.selectedEntries.length > 0 && (!requiresLap || workspace.lapSelection !== "all");
  const telemetry = useWorkspaceCarTelemetryResource({
    entryMode: "selected",
    scope: "auto",
    requireLap: requiresLap,
    limit: 5000,
    enabled: canRequestTelemetry,
  });

  if (workspace.selectedEntries.length === 0) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Brake Trace"}>
        <WidgetEmpty message="Choose at least one driver to compare brake traces." />
      </WidgetCard>
    );
  }

  if (requiresLap && workspace.lapSelection === "all") {
    return (
      <WidgetCard title={widgetOptions.title ?? "Brake Trace"}>
        <WidgetEmpty message="Choose a specific lap to compare braking points." />
      </WidgetCard>
    );
  }

  if (telemetry.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Brake Trace"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  if (!telemetry.ready) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Brake Trace"}>
        <WidgetEmpty message={telemetry.waitMessage} />
      </WidgetCard>
    );
  }

  if (telemetry.isLoading) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Brake Trace"}>
        <WidgetLoading />
      </WidgetCard>
    );
  }

  const series: LineSeries[] = workspace.selectedEntries.map((entry, index) => ({
    key: entry.id,
    label: getEntryDisplayName(entry),
    color: getEntryAccent(entry, index),
    points: downsamplePoints(buildBrakePoints(telemetry.dataByEntryId[entry.id] ?? [])),
  }));

  return (
    <WidgetCard
      title={widgetOptions.title ?? "Brake Trace"}
      description="Binary brake-on trace across the selected lap."
    >
      <SimpleLineChart series={series} emptyMessage="Brake telemetry was not available for the selected drivers." />
    </WidgetCard>
  );
}
