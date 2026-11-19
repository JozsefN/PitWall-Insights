import type widgetManifest from "../../../../shared/dashboard-widgets.json";
import type { ComponentType } from "react";

export type DashboardAudience = "session-lookback" | "live-race";
export type SessionKind = "race" | "sprint" | "qualifying" | "practice" | "other";

export type SessionWorkspaceMode = "lookback" | "simulation";

export type WidgetId = keyof typeof widgetManifest.widgets;

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

export type HeightMode = "auto" | "fill" | "sm" | "md" | "lg";

export type WidgetPolicy = {
  title: string;
  description: string;
  supportedAudiences: DashboardAudience[];
  sessionKinds?: SessionKind[];
  availabilityNote?: string;
  builderEnabled: boolean;
  category:
    | "platform"
    | "telemetry"
    | "strategy"
    | "track"
    | "replay"
    | "race"
    | "engineering";
  previewKind:
    | "status"
    | "trace"
    | "brake"
    | "pace"
    | "stints"
    | "laps"
    | "track"
    | "driver-cards"
    | "tyre-timeline"
    | "position-history"
    | "notifications"
    | "insights";
  sizing: {
    minW: number;
    minH: number;
    maxW: number;
    maxH: number;
    defaultW: number;
    defaultH: number;
    minAspect?: number;
    maxAspect?: number;
    compactBelowPx: number;
    shortBelowPx: number;
  };
  accessTier: 0 | 1 | 2 | 3;
  plannedAccessTier?: 0 | 1 | 2 | 3;
  searchTerms?: string[];
  previewLabels?: string[];
  previewDetail?: "trend" | "table" | "timing-bars" | "lap-bars" | "delta-bars";
  defaultOptions?: Record<string, unknown>;
};

export type WidgetDefinition = WidgetPolicy & {
  id: WidgetId;
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
  instanceId?: string;
  placement?: GridPlacement;
};

export type GridPlacement = { x: number; y: number; w: number; h: number };

export type LayoutGroupNode = {
  type: "group";
  direction: LayoutDirection;
  grid?: { columns: number; rowHeight: number };
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
  enabledAudiences?: DashboardAudience[];
  sessionKind?: SessionKind;
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
