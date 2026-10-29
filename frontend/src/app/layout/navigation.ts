export type NavigationItem = {
  label: string;
  to: string;
  note: string;
  section: "Explore" | "Workspace" | "System";
};

// One list keeps the header and workspace navigation in sync.
export const navigationItems: NavigationItem[] = [
  { label: "Home", to: "/", note: "Your race hub", section: "Explore" },
  {
    label: "Live Race",
    to: "/live",
    note: "Timing and race context",
    section: "Explore",
  },
  {
    label: "Story Feed",
    to: "/story-feed",
    note: "News from the paddock",
    section: "Explore",
  },
  {
    label: "Standings",
    to: "/standings",
    note: "The championship picture",
    section: "Explore",
  },
  {
    label: "Sessions",
    to: "/sessions",
    note: "Telemetry and replay",
    section: "Workspace",
  },
  {
    label: "Dashboard Builder",
    to: "/dashboard-builder",
    note: "Your reusable session layouts",
    section: "Workspace",
  },
  {
    label: "System Health",
    to: "/system/health",
    note: "Platform diagnostics",
    section: "System",
  },
];
