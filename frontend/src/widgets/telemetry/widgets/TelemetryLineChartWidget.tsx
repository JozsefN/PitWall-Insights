import {
  useWorkspaceCarTelemetryResource,
} from "../../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import {
  downsamplePoints,
  getEntryAccent,
  getEntryDisplayName,
} from "../../../features/sessions/session-utils";
import { WidgetCard } from "../../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../../shared/WidgetState";
import { SimpleLineChart } from "../components/SimpleLineChart";
import type { LineSeries, TelemetryWidgetOptions } from "../models";

export function TelemetryLineChartWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as TelemetryWidgetOptions;
  const workspace = useSessionWorkspace();
  const requiresLap = widgetOptions.requiresLap === true;
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
      <WidgetCard title={widgetOptions.title ?? "Telemetry"}>
        <WidgetEmpty message="Choose at least one driver to unlock telemetry widgets." />
      </WidgetCard>
    );
  }

  if (requiresLap && workspace.lapSelection === "all") {
    return (
      <WidgetCard title={widgetOptions.title ?? "Telemetry"}>
        <WidgetEmpty message="Choose a specific lap to render lap-scoped telemetry." />
      </WidgetCard>
    );
  }

  if (telemetry.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Telemetry"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  if (!telemetry.ready) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Telemetry"}>
        <WidgetEmpty message={telemetry.waitMessage} />
      </WidgetCard>
    );
  }

  if (telemetry.isLoading) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Telemetry"}>
        <WidgetLoading />
      </WidgetCard>
    );
  }

  const metric = widgetOptions.metric ?? "speed_kph";
  const series: LineSeries[] = workspace.selectedEntries.map((entry, index) => ({
    key: entry.id,
    label: getEntryDisplayName(entry),
    color: getEntryAccent(entry, index),
    points: downsamplePoints(
      (telemetry.dataByEntryId[entry.id] ?? [])
        .filter((sample) => sample[metric] != null)
        .map((sample) => ({
          x: sample.session_time_ms,
          y: Number(sample[metric]),
        })),
    ),
  }));

  return (
    <WidgetCard
      title={widgetOptions.title ?? "Telemetry"}
      description={`${widgetOptions.metricLabel ?? "Telemetry"} trace${widgetOptions.unit ? ` - ${widgetOptions.unit}` : ""}`}
    >
      <SimpleLineChart series={series} emptyMessage="Telemetry samples were not available for the selected drivers." />
    </WidgetCard>
  );
}
