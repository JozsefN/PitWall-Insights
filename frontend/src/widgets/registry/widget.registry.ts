import { widgetCatalog } from "./widget.catalog";
import type { WidgetDefinition, WidgetId } from "./widget.types";
import { HealthOverviewWidget } from "../overlays/health-overview/HealthOverviewWidget";
import { SessionsSummaryWidget } from "../overlays/sessions-summary/SessionsSummaryWidget";
import {
  BrakeTraceChartWidget,
  LapTableWidget,
  LapTimeTrendWidget,
  SessionTrackMapWidget,
  StintAnalysisWidget,
  TelemetryLineChartWidget,
} from "../telemetry";
import { ReplayTrackMapWidget } from "../track-map";
import { ReplayDriverCardsWidget } from "../replay/ReplayWidgets";

const components = {
  "health-overview": HealthOverviewWidget,
  "sessions-summary": SessionsSummaryWidget,
  "telemetry-line-chart": TelemetryLineChartWidget,
  "brake-trace-chart": BrakeTraceChartWidget,
  "lap-time-trend": LapTimeTrendWidget,
  "stint-analysis": StintAnalysisWidget,
  "lap-table": LapTableWidget,
  "session-track-map": SessionTrackMapWidget,
  "replay-track-map": ReplayTrackMapWidget,
  "replay-driver-cards": ReplayDriverCardsWidget,
} satisfies Record<WidgetId, WidgetDefinition["component"]>;

export const widgetRegistry = Object.fromEntries(
  (Object.keys(components) as WidgetId[]).map((id) => [
    id,
    { id, ...widgetCatalog[id], component: components[id] },
  ]),
) as Record<WidgetId, WidgetDefinition>;
