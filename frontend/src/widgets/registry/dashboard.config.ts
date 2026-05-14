import type { DashboardConfig, LayoutRecord } from "./widget.types";

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

export const builtinSessionLayouts: LayoutRecord[] = [
  {
    id: "builtin:compare-lap",
    name: "Compare Lap",
    description: "Overlay speed, throttle, and braking traces for a chosen lap.",
    source: "builtin",
    audience: "session-lookback",
    schemaVersion: 1,
    updatedAt: "2026-04-12T00:00:00Z",
    config: {
      id: "compare-lap",
      title: "Compare Lap",
      subtitle: "Choose a lap, then compare the telemetry traces for your selected drivers.",
      sections: [
        {
          id: "lap-traces",
          title: "Lap Traces",
          description: "Speed, throttle, and brake overlays update once a specific lap is selected.",
          layout: {
            type: "group",
            direction: "row",
            gap: 20,
            children: [
              {
                type: "group",
                direction: "column",
                gap: 20,
                children: [
                  {
                    type: "widget",
                    widgetId: "telemetry-line-chart",
                    width: "full",
                    height: "md",
                    minHeight: 280,
                    options: {
                      title: "Speed Trace",
                      metric: "speed_kph",
                      metricLabel: "Speed",
                      unit: "kph",
                      requiresLap: true,
                    },
                  },
                  {
                    type: "widget",
                    widgetId: "telemetry-line-chart",
                    width: "full",
                    height: "md",
                    minHeight: 280,
                    options: {
                      title: "Throttle Trace",
                      metric: "throttle_pct",
                      metricLabel: "Throttle",
                      unit: "%",
                      requiresLap: true,
                    },
                  },
                ],
              },
              {
                type: "widget",
                widgetId: "brake-trace-chart",
                width: "1/3",
                height: "lg",
                minHeight: 580,
                options: {
                  title: "Brake Trace",
                  requiresLap: true,
                },
              },
            ],
          },
        },
      ],
    },
  },
  {
    id: "builtin:session-trends",
    name: "Session Trends",
    description: "Track-wide lookback with lap pace comparison, lap data, and full session lines.",
    source: "builtin",
    audience: "session-lookback",
    schemaVersion: 1,
    updatedAt: "2026-04-12T00:00:00Z",
    config: {
      id: "session-trends",
      title: "Session Trends",
      subtitle: "Full-session overview for driver lap pace, selected entries, and circuit shape.",
      sections: [
        {
          id: "headline",
          title: "Session Overview",
          description: "Lap pace stays in full-session mode even when lap detail is available elsewhere.",
          layout: {
            type: "group",
            direction: "row",
            gap: 20,
            children: [
              {
                type: "widget",
                widgetId: "lap-time-trend",
                width: "2/3",
                height: "lg",
                minHeight: 320,
                options: {
                  title: "Driver Lap Pace",
                },
              },
              {
                type: "widget",
                widgetId: "session-track-map",
                width: "1/3",
                height: "lg",
                minHeight: 320,
                options: {
                  title: "Session Track Map",
                  scope: "session",
                },
              },
            ],
          },
        },
        {
          id: "details",
          title: "Lap Detail Table",
          description: "A compact lap list for the selected drivers.",
          layout: {
            type: "widget",
            widgetId: "lap-table",
            width: "full",
            height: "lg",
            minHeight: 360,
          },
        },
      ],
    },
  },
  {
    id: "builtin:stint-strategy",
    name: "Stint Strategy",
    description: "Compare stint pace, compound windows, and degradation across selected drivers.",
    source: "builtin",
    audience: "session-lookback",
    schemaVersion: 1,
    updatedAt: "2026-04-12T00:00:00Z",
    config: {
      id: "stint-strategy",
      title: "Stint Strategy",
      subtitle: "Absolute lap-number stint analysis with compound and filtering controls.",
      sections: [
        {
          id: "stints",
          title: "Stint Analysis",
          description: "Each stint starts on its real session lap, not a reset-to-zero axis.",
          layout: {
            type: "widget",
            widgetId: "stint-analysis",
            width: "full",
            height: "lg",
            minHeight: 620,
          },
        },
        {
          id: "lap-detail",
          title: "Lap Detail",
          description: "Raw lap rows stay nearby for checking individual laps behind the stint view.",
          layout: {
            type: "widget",
            widgetId: "lap-table",
            width: "full",
            height: "md",
            minHeight: 320,
          },
        },
      ],
    },
  },
  {
    id: "builtin:replay-command",
    name: "Replay Command",
    description: "Race-control style replay map with driver cards for simulation mode.",
    source: "builtin",
    audience: "live-race",
    schemaVersion: 1,
    updatedAt: "2026-04-12T00:00:00Z",
    config: {
      id: "replay-command",
      title: "Replay Command",
      subtitle: "Simulation layouts only expose widgets that can live inside the replay clock.",
      sections: [
        {
          id: "replay-primary",
          title: "Replay Surface",
          description: "Track position and live-style telemetry cards update from the current session time.",
          layout: {
            type: "group",
            direction: "row",
            gap: 20,
            children: [
              {
                type: "widget",
                widgetId: "replay-track-map",
                width: "2/3",
                height: "lg",
                minHeight: 360,
              },
              {
                type: "widget",
                widgetId: "replay-driver-cards",
                width: "1/3",
                height: "lg",
                minHeight: 360,
              },
            ],
          },
        },
        {
          id: "replay-strategy",
          title: "Strategy",
          description: "Completed stint laps update with the replay clock.",
          layout: {
            type: "widget",
            widgetId: "stint-analysis",
            width: "full",
            height: "lg",
            minHeight: 560,
          },
        },
      ],
    },
  },
  {
    id: "builtin:replay-focus",
    name: "Replay Focus",
    description: "A tighter replay stack for following movement and telemetry together.",
    source: "builtin",
    audience: "live-race",
    schemaVersion: 1,
    updatedAt: "2026-04-12T00:00:00Z",
    config: {
      id: "replay-focus",
      title: "Replay Focus",
      subtitle: "Compact replay surface with a larger track map and tighter driver telemetry.",
      sections: [
        {
          id: "replay-focus-main",
          title: "Focused Replay",
          description: "Best for staying close to track movement while keeping telemetry cards readable.",
          layout: {
            type: "group",
            direction: "column",
            gap: 20,
            children: [
              {
                type: "widget",
                widgetId: "replay-track-map",
                width: "full",
                height: "lg",
                minHeight: 360,
              },
              {
                type: "widget",
                widgetId: "replay-driver-cards",
                width: "full",
                height: "md",
                minHeight: 220,
              },
            ],
          },
        },
      ],
    },
  },
];
