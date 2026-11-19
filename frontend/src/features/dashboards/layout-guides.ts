import type {
  DashboardAudience,
  SessionKind,
} from "../../widgets/registry/widget.types";

export const raceViewerLayoutId = "builtin:race-spectator";

const recommended: Partial<
  Record<SessionKind, Record<DashboardAudience, string>>
> = {
  race: {
    "live-race": raceViewerLayoutId,
    "session-lookback": "builtin:race-review",
  },
  sprint: {
    "live-race": "builtin:sprint-replay",
    "session-lookback": "builtin:sprint-review",
  },
  qualifying: {
    "live-race": "builtin:qualifying-replay",
    "session-lookback": "builtin:qualifying-review",
  },
  practice: {
    "live-race": "builtin:practice-replay",
    "session-lookback": "builtin:practice-review",
  },
};

export function recommendedLayoutId(
  mode: DashboardAudience,
  kind?: SessionKind,
) {
  return kind ? recommended[kind]?.[mode] : undefined;
}

const guides: Record<string, { label: string; summary: string }> = {
  [raceViewerLayoutId]: {
    label: "Start here",
    summary: "Follow cars, race updates and radio.",
  },
  "builtin:compare-lap": {
    label: "Lap comparison",
    summary: "Compare speed, throttle and braking on a lap.",
  },
  "builtin:session-trends": {
    label: "Session overview",
    summary: "See who's faster across several laps.",
  },
  "builtin:stint-strategy": {
    label: "Tyre strategy",
    summary: "See how lap pace changes across tyre sets.",
  },
  "builtin:replay-command": {
    label: "Detailed replay",
    summary: "Watch car positions, pedal inputs and stint pace.",
  },
  "builtin:replay-focus": {
    label: "Track map & speed",
    summary: "Follow cars with speed, gear and braking cards.",
  },
  "builtin:engineering-desk": {
    label: "Engineering",
    summary: "Inspect braking, traffic and tyre workload.",
  },
  "builtin:strategy-desk": {
    label: "Pit strategy",
    summary: "Track rival gaps, tyres and pit windows.",
  },
  "builtin:race-strategy": {
    label: "Strategy model",
    summary: "See the pit call change with tyre pace and race warnings.",
  },
  "builtin:race-strategy-review": {
    label: "Strategy scenarios",
    summary: "Explore pit rejoin and projected race order.",
  },
  "builtin:race-review": {
    label: "Post-race review",
    summary: "Compare pace and review race-control reports.",
  },
  "builtin:qualifying-review": {
    label: "Qualifying review",
    summary: "Compare Q1, Q2 and Q3 with lap telemetry.",
  },
  "builtin:sprint-review": {
    label: "Sprint review",
    summary: "Review sprint pace, running order and tyre sets.",
  },
  "builtin:sprint-replay": {
    label: "Race order & radio",
    summary: "Follow the sprint with timing, car positions and radio.",
  },
  "builtin:qualifying-replay": {
    label: "Qualifying timing",
    summary:
      "Watch lap times and sector differences appear as drivers finish their runs.",
  },
  "builtin:practice-review": {
    label: "Long-run pace",
    summary: "Compare clean runs, tyre degradation and braking.",
  },
  "builtin:practice-replay": {
    label: "Timing & tyre runs",
    summary: "Follow practice runs, tyre pace and braking evidence.",
  },
};

export function getLayoutGuide(id: string) {
  return guides[id];
}
