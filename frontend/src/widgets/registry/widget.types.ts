import type { ComponentType } from "react";

export type DashboardAudience =
  | "session-lookback"
  | "live-race";

export type SessionWorkspaceMode =
  | "lookback"
  | "simulation";

export type WidgetId =
  | "health-overview"
  | "sessions-summary"
  | "telemetry-line-chart"
  | "brake-trace-chart"
  | "lap-time-trend"
  | "lap-table"
  | "session-track-map"
  | "replay-track-map"
  | "replay-driver-cards";

export type LayoutDirection = "row" | "column";

export type WidthMode =
  | "auto"
  | "fill"
  | "full"
  | "1/4"
  | "1/3"
  | "1/2"
  | "2/3"
  | "3/4";

export type HeightMode =
  | "auto"
  | "fill"
  | "sm"
  | "md"
  | "lg";

export type WidgetDefinition = {
  id: WidgetId;
  title: string;
  description?: string;
  supportedAudiences?: DashboardAudience[];
  component: ComponentType<{ options?: Record<string, unknown> }>;
};

export type LayoutWidgetNode = {
  type: "widget";
  widgetId: WidgetId;
  options?: Record<string, unknown>;
  width?: WidthMode;
  height?: HeightMode;
  minHeight?: number;
  maxHeight?: number;
  grow?: number;
  className?: string;
};

export type LayoutGroupNode = {
  type: "group";
  direction: LayoutDirection;
  gap?: number;
  children: Array<LayoutGroupNode | LayoutWidgetNode>;
};

export type SectionLayoutNode = LayoutGroupNode | LayoutWidgetNode;

export type DashboardSection = {
  id: string;
  title?: string;
  description?: string;
  layout: SectionLayoutNode;
};

export type DashboardConfig = {
  id: string;
  title?: string;
  subtitle?: string;
  sections: DashboardSection[];
};

export type LayoutSource = "builtin" | "user";

export type LayoutRecord = {
  id: string;
  name: string;
  description?: string | null;
  source: LayoutSource;
  audience: DashboardAudience;
  schemaVersion: number;
  config: DashboardConfig;
  updatedAt: string;
  storageId?: string;
};
