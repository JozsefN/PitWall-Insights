import type { DashboardConfig } from "./widget.types";

export const homeDashboardConfig: DashboardConfig = {
  id: "home",
  title: "Overview",
  subtitle: "Operational visibility across platform services and sessions.",
  sections: [
    {
      id: "primary",
      title: "Platform",
      description: "Core platform status and activity.",
      layout: {
        type: "group",
        direction: "row",
        gap: 20,
        children: [
          {
            type: "widget",
            widgetId: "health-overview",
            width: "1/2",
            height: "md",
            minHeight: 260,
          },
          {
            type: "widget",
            widgetId: "sessions-summary",
            width: "1/2",
            height: "md",
            minHeight: 260,
          },
        ],
      },
    },
  ],
};