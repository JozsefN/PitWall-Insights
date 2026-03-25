import type { ComponentType } from "react";

export type WidgetId =
  | "health-overview"
  | "sessions-summary";

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
  component: ComponentType;
};

export type LayoutWidgetNode = {
  type: "widget";
  widgetId: WidgetId;
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