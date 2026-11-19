import type {
  DashboardConfig,
  LayoutRecord,
  SessionKind,
  WidgetId,
} from "./widget.types";
import type { TrackMapLayer } from "../track-map/models";

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
    description:
      "Overlay speed, throttle, and braking traces for a chosen lap.",
    source: "builtin",
    audience: "session-lookback",
    schemaVersion: 1,
    updatedAt: "2026-04-12T00:00:00Z",
    config: {
      id: "compare-lap",
      title: "Compare Lap",
      subtitle:
        "Choose a lap, then compare the telemetry traces for your selected drivers.",
      sections: [
        {
          id: "lap-traces",
          title: "Lap Traces",
          description:
            "Speed, throttle, and brake overlays update once a specific lap is selected.",
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
    description:
      "Track-wide lookback with lap pace comparison, lap data, and full session lines.",
    source: "builtin",
    audience: "session-lookback",
    schemaVersion: 1,
    updatedAt: "2026-04-12T00:00:00Z",
    config: {
      id: "session-trends",
      title: "Session Trends",
      subtitle:
        "Full-session overview for driver lap pace, selected entries, and circuit shape.",
      sections: [
        {
          id: "headline",
          title: "Session Overview",
          description:
            "Lap pace stays in full-session mode even when lap detail is available elsewhere.",
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
    description:
      "Compare stint pace, compound windows, and degradation across selected drivers.",
    source: "builtin",
    audience: "session-lookback",
    schemaVersion: 1,
    updatedAt: "2026-04-12T00:00:00Z",
    config: {
      id: "stint-strategy",
      title: "Stint Strategy",
      subtitle:
        "Absolute lap-number stint analysis with compound and filtering controls.",
      sections: [
        {
          id: "stints",
          title: "Stint Analysis",
          description:
            "Each stint starts on its real session lap, not a reset-to-zero axis.",
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
          description:
            "Raw lap rows stay nearby for checking individual laps behind the stint view.",
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
    description:
      "Race-control style replay map with driver cards for simulation mode.",
    source: "builtin",
    audience: "live-race",
    schemaVersion: 1,
    updatedAt: "2026-04-12T00:00:00Z",
    config: {
      id: "replay-command",
      title: "Replay Command",
      subtitle:
        "Simulation layouts only expose widgets that can live inside the replay clock.",
      sections: [
        {
          id: "replay-primary",
          title: "Replay Surface",
          description:
            "Track position and live-style telemetry cards update from the current session time.",
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
          title: "Tyre stints",
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
    description:
      "A tighter replay stack for following movement and telemetry together.",
    source: "builtin",
    audience: "live-race",
    schemaVersion: 1,
    updatedAt: "2026-04-12T00:00:00Z",
    config: {
      id: "replay-focus",
      title: "Replay Focus",
      subtitle:
        "Compact replay surface with a larger track map and tighter driver telemetry.",
      sections: [
        {
          id: "replay-focus-main",
          title: "Focused Replay",
          description:
            "Best for staying close to track movement while keeping telemetry cards readable.",
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
                minHeight: 306,
              },
            ],
          },
        },
      ],
    },
  },
];

// Stable factory IDs remain immutable. These presets also appear in session selection.
function insightPreset(
  id: string,
  name: string,
  audience: LayoutRecord["audience"],
  panels: Array<WidgetId | { widgetId: WidgetId; options: Record<string, unknown> }>,
  sessionKind?: SessionKind,
  description = "Physics-informed estimates, reported race context and transparent evidence.",
  mapLayer?: TrackMapLayer,
  featurePanel?: WidgetId,
): LayoutRecord {
  return {
    id: `builtin:${id}`,
    name,
    description,
    source: "builtin",
    audience,
    schemaVersion: 2,
    updatedAt: "2026-11-19T00:00:00Z",
    config: {
      id,
      title: name,
      sessionKind,
      sections: [
        ...(mapLayer
          ? [
              {
                id: "circuit",
                layout: {
                  type: "group" as const,
                  direction: "row" as const,
                  grid: { columns: 12, rowHeight: 48 },
                  gap: 12,
                  children: [
                    {
                      type: "widget" as const,
                      widgetId:
                        audience === "live-race"
                          ? ("replay-track-map" as const)
                          : ("session-track-map" as const),
                      instanceId: `${id}-map`,
                      placement: { x: 0, y: 0, w: 12, h: 10 },
                      options: { mapLayer },
                    },
                  ],
                },
              },
            ]
          : []),
        ...(featurePanel ? [{
          id: "featured-panel",
          layout: {
            type: "group" as const,
            direction: "row" as const,
            grid: { columns: 12, rowHeight: 48 },
            gap: 12,
            children: [{ type: "widget" as const, widgetId: featurePanel, instanceId: `${id}-featured`, placement: { x: 0, y: 0, w: 12, h: 10 } }],
          },
        }] : []),
        {
          id: "race-desk",
          layout: {
            type: "group",
            direction: "row",
            grid: { columns: 12, rowHeight: 48 },
            gap: 12,
            children: panels.map((panel, index) => ({
              type: "widget",
              ...(typeof panel === "string" ? { widgetId: panel } : panel),
              instanceId: `${id}-${index}`,
              placement: {
                x: (index % 2) * 6,
                y: Math.floor(index / 2) * 8,
                w: 6,
                h: 8,
              },
            })),
          },
        },
      ],
    },
  };
}
builtinSessionLayouts.push(
  insightPreset("sprint-review", "Sprint review", "session-lookback",
    ["position-history", "lap-time-trend", "tyre-timeline", "lap-table"],
    "sprint", "Compare the sprint's running order, pace and tyre sets after the finish."),
  insightPreset("sprint-replay", "Sprint replay", "live-race",
    ["position-history", "replay-timing-board", "tyre-timeline", "team-radio"],
    "sprint", "Follow the field, lap times and radio during the sprint.", "track"),
  insightPreset("qualifying-replay", "Qualifying replay", "live-race",
    ["replay-timing-board", "replay-driver-cards", "team-radio"],
    "qualifying", "Follow timed laps and split differences as qualifying or sprint qualifying unfolds.", "track"),
  insightPreset("practice-review", "Practice analysis", "session-lookback",
    ["lap-time-trend", "brake-trace-chart", "pace-context", "lap-table"],
    "practice", "Review long-run pace, tyre degradation and braking on selected laps.", undefined, "stint-analysis"),
  insightPreset("practice-replay", "Practice replay", "live-race",
    ["replay-timing-board", "braking-analysis", "stint-performance", "tyre-timeline"],
    "practice", "Watch practice runs and compare lap pace, braking and tyre trends as they happen.", "track"),
  insightPreset(
    "race-strategy",
    "Race strategy",
    "live-race",
    ["strategy-call", "intervention-risk", "tyre-crossover", "tyre-outlook", "rival-pit-scenarios", "rival-comparison", "tyre-timeline", "position-history"],
    "race",
    "Follow the pit call, tyre pace and incident risk as the replay advances.",
  ),
  insightPreset(
    "race-spectator",
    "Race viewer",
    "live-race",
    [
      { widgetId: "race-notifications", options: { title: "Race updates", includeCandidates: false, maxItems: 5, eventTypes: ["yellow_flag", "green_flag", "safety_car", "red_flag", "pit_stop", "overtake"] } },
      "team-radio",
    ],
    "race",
    "Follow selected drivers on the map, see flags and pit stops, and listen to team radio.",
    "track",
  ),
  insightPreset(
    "engineering-desk",
    "Engineering desk",
    "live-race",
    [
      "driver-overview",
      "wake-exposure",
      "braking-analysis",
      "tyre-workload",
      "stint-performance",
      "model-quality",
    ],
    "race",
    "Choose drivers, then seek to a green-flag lap. Follow their positions on the map and compare braking, traffic and tyre workload.",
    "track",
  ),
  insightPreset(
    "strategy-desk",
    "Strategy desk",
    "live-race",
    [
      "race-notifications",
      "pit-scenarios",
      "closing-gaps",
      "stint-performance",
      "overtake-opportunities",
      "driver-comparison",
      "tyre-timeline",
      "position-history",
    ],
    "race",
    "Follow track conditions, rivals and the pit window during green-flag running.",
    "weather",
  ),
  insightPreset(
    "race-review",
    "Race review",
    "session-lookback",
    [
      "pace-context",
      "stint-performance",
      "driver-comparison",
      "incident-reports",
      "tyre-timeline",
      "position-history",
    ],
    "race",
    "Compare completed race laps and review where the selected drivers ran.",
    "track",
  ),
  insightPreset(
    "qualifying-review",
    "Qualifying review",
    "session-lookback",
    [
      "lookback-driver-cards",
      "lap-segment-review",
      "team-radio",
      "weather-history",
    ],
    "qualifying",
    "Choose a timed lap and compare its splits against the whole field. Review Q1, Q2 and Q3 results below.",
    undefined,
    "qualifying-lap-map",
  ),
  insightPreset(
    "race-strategy-review",
    "Race strategy review",
    "live-race",
    [
      "racecraft-review",
      "pit-benchmark",
      "race-pace-forecast",
      "incident-reports",
      "team-radio",
      "weather-history",
    ],
    "race",
    "Review live-to-the-clock strategy scenarios, pit rejoin and racecraft from timing and reports.",
  ),
);
