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
import { insightComponents } from "../insights/insight.registry";
import { reviewComponents } from "../review/review.registry";
import { QualifyingLapWidget } from "../review/QualifyingLapWidget";
import { PositionHistoryWidget, TyreTimelineWidget } from "../race-timing/TimingPanels";
import { ReplayTimingBoard } from "../race-timing/ReplayTimingBoard";
import { InterventionRiskWidget, StrategyCallWidget, TyreOutlookWidget } from "../replay-strategy/StrategyPanels";
import { RivalComparisonWidget, RivalPitScenariosWidget } from "../replay-strategy/RivalStrategyPanels";
import { TyreCrossoverWidget } from "../replay-strategy/TyreCrossoverWidget";

const components = {
  ...insightComponents,
  ...reviewComponents,
  "qualifying-lap-map": QualifyingLapWidget,
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
  "tyre-timeline": TyreTimelineWidget,
  "position-history": PositionHistoryWidget,
  "replay-timing-board": ReplayTimingBoard,
  "strategy-call": StrategyCallWidget,
  "intervention-risk": InterventionRiskWidget,
  "tyre-outlook": TyreOutlookWidget,
  "tyre-crossover": TyreCrossoverWidget,
  "rival-comparison": RivalComparisonWidget,
  "rival-pit-scenarios": RivalPitScenariosWidget,
} satisfies Record<WidgetId, WidgetDefinition["component"]>;

export const widgetRegistry = Object.fromEntries(
  (Object.keys(components) as WidgetId[]).map((id) => [
    id,
    { id, ...widgetCatalog[id], component: components[id] },
  ]),
) as Record<WidgetId, WidgetDefinition>;
