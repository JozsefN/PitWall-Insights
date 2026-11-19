import { widgetCatalog } from "../../widgets/registry/widget.catalog.ts";
import type {
  DashboardAudience,
  DashboardConfig,
  LayoutRecord,
  SectionLayoutNode,
  SessionKind,
  WidgetId,
} from "../../widgets/registry/widget.types.ts";

export const sessionKinds = [
  "race",
  "sprint",
  "qualifying",
  "practice",
  "other",
] as const;
export const sessionKindLabel: Record<SessionKind, string> = {
  race: "Grand Prix",
  sprint: "Sprint",
  qualifying: "Qualifying",
  practice: "Practice",
  other: "Other sessions",
};
export const modeLabel: Record<DashboardAudience, string> = {
  "session-lookback": "Lookback",
  "live-race": "Replay",
};

export function classifySession(session: {
  session_name: string;
  session_type?: string | null;
}): SessionKind {
  const name = session.session_name.trim().toLowerCase();
  const type = session.session_type?.trim().toLowerCase();
  if (/qualifying|shootout/.test(name)) return "qualifying";
  if (name === "sprint" || name === "sprint race") return "sprint";
  if (name === "race" || name === "grand prix") return "race";
  if (name.includes("practice")) return "practice";
  if (type === "qualifying" || type === "race" || type === "practice")
    return type;
  return "other";
}

export function widgetIds(config: DashboardConfig): WidgetId[] {
  function collect(node: SectionLayoutNode): WidgetId[] {
    return node.type === "group"
      ? node.children.flatMap(collect)
      : [node.widgetId];
  }
  return [
    ...new Set(config.sections.flatMap((section) => collect(section.layout))),
  ];
}

export function layoutModes(
  layout: Pick<LayoutRecord, "audience" | "config">,
): DashboardAudience[] {
  return layout.config.enabledAudiences ?? [layout.audience];
}

export function supportedSessionKinds(
  ids: WidgetId[],
  target?: SessionKind,
): SessionKind[] {
  return sessionKinds.filter(
    (kind) =>
      (!target || kind === target) &&
      ids.every((id) => widgetCatalog[id]?.sessionKinds?.includes(kind)),
  );
}

export function modesText(modes: readonly DashboardAudience[]) {
  return modes.length === 2
    ? "Lookback + Replay"
    : modes.length
      ? `${modeLabel[modes[0]]} only`
      : "Unavailable";
}

export function sessionKindsText(kinds: readonly SessionKind[]) {
  if (kinds.length === sessionKinds.length) return "All session types";
  return kinds.length > 0
    ? `${kinds.map((kind) => sessionKindLabel[kind]).join(" · ")}${kinds.length === 1 ? " only" : ""}`
    : "No compatible session types";
}

export function widgetBlockReason(
  id: WidgetId,
  modes: DashboardAudience[],
  compatibleKinds: readonly SessionKind[],
): string | undefined {
  const policy = widgetCatalog[id];
  if (policy && !policy.builderEnabled)
    return `${policy.title} is a platform panel and is unavailable in session layouts.`;
  if (!policy) return `Panel ${id} is unavailable in session layouts.`;
  if (modes.some((mode) => !policy.supportedAudiences.includes(mode)))
    return `${policy.title} is available in ${modesText(policy.supportedAudiences)}.`;
  if (!compatibleKinds.some((kind) => policy.sessionKinds?.includes(kind)))
    return `${policy.title} supports ${sessionKindsText(policy.sessionKinds ?? [])}.`;
}

export function layoutCompatibilityReason(
  layout: Pick<LayoutRecord, "audience" | "config">,
  mode: DashboardAudience,
  kind?: SessionKind,
) {
  const modes = layoutModes(layout);
  if (!modes.includes(mode))
    return `Saved for ${modesText(modes)}.`;
  const ids = widgetIds(layout.config);
  const target = layout.config.sessionKind;
  if (kind && target && target !== kind)
    return `This layout is set to ${sessionKindsText([target])}.`;
  const enabledKinds = kind ? [kind] : target ? [target] : sessionKinds;
  for (const id of ids) {
    const reason = widgetBlockReason(id, modes, enabledKinds);
    if (reason) return reason;
  }
  if (!supportedSessionKinds(ids, target).length)
    return "These panels have no shared session type. Edit the layout to resolve the conflict.";
}
