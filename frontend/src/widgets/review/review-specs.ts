import type { ReviewGroup } from "../../features/session-review/contracts";
import type {
  DashboardConfig,
  SectionLayoutNode,
} from "../registry/widget.types";

export const reviewPanels = {
  "lookback-driver-cards": {
    title: "Qualifying driver cards",
    group: "drivers",
  },
  "lap-segment-review": { title: "Lap segment comparison", group: "drivers" },
  "team-radio": { title: "Team radio", group: "radio" },
  "racecraft-review": { title: "Passes & battles", group: "racecraft" },
  "race-pace-forecast": { title: "Race pace & projection", group: "pace" },
  "pit-benchmark": { title: "Pit loss & rejoin", group: "pit" },
  "incident-reports": { title: "Contact & track limits", group: "incidents" },
  "weather-history": { title: "Rain & wind history", group: "weather" },
  "track-surface": { title: "Track surface map", group: "surface" },
} as const satisfies Record<string, { title: string; group: ReviewGroup }>;
export type ReviewPanelId = keyof typeof reviewPanels;

export const reviewPanelGuide: Record<ReviewPanelId, string> = {
  "lookback-driver-cards":
    "After qualifying, compare each driver's best completed lap in Q1, Q2 and Q3.",
  "lap-segment-review":
    "Choose two completed laps and prepare their telemetry. Compare distance segments to see where one lap gained time.",
  "team-radio":
    "Listen to clips published for the selected drivers. ≈ marks an estimated recording time. Feed marks when the source listed the clip, which may be later than the conversation.",
  "racecraft-review":
    "Use mid-race to separate sustained passes from close battles. Check flags and pit cycles when interpreting a change in order.",
  "race-pace-forecast":
    "Use after clean race laps and during green running. Try different lap horizons to test how assumed pace changes the projection.",
  "pit-benchmark":
    "Compare the projected rejoin with a rival's gap before committing to a stop. Look at sample counts alongside the median.",
  "incident-reports":
    "Use to check whether race control reported contact, damage or a track-limits event around the time you are viewing.",
  "weather-history":
    "Check the reported rain and wind timeline before comparing laps from different parts of the session.",
  "track-surface":
    "Register a circuit profile for this session to compare reported car positions with surveyed surfaces and recovery access.",
};

export function requestedReviewGroups(config: DashboardConfig) {
  function collect(node: SectionLayoutNode): ReviewGroup[] {
    if (node.type === "group") return node.children.flatMap(collect);
    if (node.widgetId === "team-radio") return [];
    if (
      node.widgetId === "replay-track-map" ||
      node.widgetId === "session-track-map"
    ) {
      const layer = node.options?.mapLayer;
      if (layer === "weather" || layer === "flags") return [layer];
    }
    const spec = reviewPanels[node.widgetId as ReviewPanelId];
    return spec
      ? node.widgetId === "pit-benchmark"
        ? [spec.group, "incidents"]
        : [spec.group]
      : [];
  }
  return [
    ...new Set(config.sections.flatMap((section) => collect(section.layout))),
  ].sort();
}
