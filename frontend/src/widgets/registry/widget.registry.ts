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
  "telemetry-line-chart": {
    id: "telemetry-line-chart",
    title: "Telemetry Line Chart",
    description: "Speed or throttle overlays for selected drivers.",
    supportedAudiences: ["session-lookback"],
    component: TelemetryLineChartWidget,
  },
  "brake-trace-chart": {
    id: "brake-trace-chart",
    title: "Brake Trace",
    description: "Brake-on overlays for a specific lap.",
    supportedAudiences: ["session-lookback"],
    component: BrakeTraceChartWidget,
  },
  "lap-time-trend": {
    id: "lap-time-trend",
    title: "Driver Lap Pace",
    description: "Lap-time comparison with clean-lap filters, references, and hover values.",
    supportedAudiences: ["session-lookback"],
    component: LapTimeTrendWidget,
  },
  "stint-analysis": {
    id: "stint-analysis",
    title: "Stint Analysis",
    description: "Stint pace, compound windows, and degradation against absolute lap numbers.",
    supportedAudiences: ["session-lookback", "live-race"],
    component: StintAnalysisWidget,
  },
  "lap-table": {
    id: "lap-table",
    title: "Lap Table",
    description: "Lap-by-lap data for selected drivers.",
    supportedAudiences: ["session-lookback"],
    component: LapTableWidget,
  },
  "session-track-map": {
    id: "session-track-map",
    title: "Session Track Map",
    description: "Position traces for selected drivers.",
    supportedAudiences: ["session-lookback"],
    component: SessionTrackMapWidget,
  },
  "replay-track-map": {
    id: "replay-track-map",
    title: "Replay Track Map",
    description: "Current car positions against the replay clock.",
    supportedAudiences: ["live-race"],
    component: ReplayTrackMapWidget,
  },
  "replay-driver-cards": {
    id: "replay-driver-cards",
    title: "Replay Driver Cards",
    description: "Live-style driver telemetry cards.",
    supportedAudiences: ["live-race"],
    component: ReplayDriverCardsWidget,
  },
};
