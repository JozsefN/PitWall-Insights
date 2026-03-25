import type { WidgetDefinition, WidgetId } from "./widget.types";
import { HealthOverviewWidget } from "../health-overview/HealthOverviewWidget";
import { SessionsSummaryWidget } from "../sessions-summary/SessionsSummaryWidget";

export const widgetRegistry: Record<WidgetId, WidgetDefinition> = {
  "health-overview": {
    id: "health-overview",
    title: "System Health",
    description: "Current health signals across core services.",
    component: HealthOverviewWidget,
  },
  "sessions-summary": {
    id: "sessions-summary",
    title: "Sessions",
    description: "Session volume and recent activity.",
    component: SessionsSummaryWidget,
  },
};