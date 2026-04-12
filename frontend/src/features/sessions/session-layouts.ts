import type { LayoutDto } from "../../data/contracts/layouts.contracts";
import { builtinSessionLayouts } from "../../widgets/registry/dashboard.config";
import { widgetRegistry } from "../../widgets/registry/widget.registry";
import type {
  DashboardAudience,
  LayoutGroupNode,
  LayoutRecord,
  LayoutWidgetNode,
  SectionLayoutNode,
  SessionWorkspaceMode,
} from "../../widgets/registry/widget.types";

export type ResolvedLayoutRecord = LayoutRecord & {
  isValid: boolean;
  invalidReason?: string;
};

export function getAudienceForMode(mode: SessionWorkspaceMode): DashboardAudience {
  return mode === "simulation" ? "live-race" : "session-lookback";
}

export function toUserLayoutRecord(layout: LayoutDto): LayoutRecord {
  return {
    id: `user:${layout.id}`,
    name: layout.name,
    description: layout.description,
    source: "user",
    audience: layout.audience,
    schemaVersion: layout.schemaVersion,
    config: layout.config,
    updatedAt: layout.updatedAt,
    storageId: layout.id,
  };
}

export function resolveWorkspaceLayouts(
  userLayouts: LayoutDto[] | undefined,
  audience: DashboardAudience,
): ResolvedLayoutRecord[] {
  return [...builtinSessionLayouts, ...(userLayouts ?? []).map(toUserLayoutRecord)]
    .filter((layout) => layout.audience === audience)
    .map((layout) => validateResolvedLayout(layout));
}

export function getResolvedLayoutById(
  layoutId: string | null,
  layouts: ResolvedLayoutRecord[],
): ResolvedLayoutRecord | null {
  if (!layoutId) {
    return null;
  }

  return layouts.find((layout) => layout.id === layoutId) ?? null;
}

function validateResolvedLayout(layout: LayoutRecord): ResolvedLayoutRecord {
  const invalidReason = findInvalidNodeReason(layout.audience, layout.config.sections.flatMap((section) => [section.layout]));

  if (invalidReason) {
    return {
      ...layout,
      isValid: false,
      invalidReason,
    };
  }

  return {
    ...layout,
    isValid: true,
  };
}

function findInvalidNodeReason(
  audience: DashboardAudience,
  nodes: SectionLayoutNode[],
): string | undefined {
  for (const node of nodes) {
    const reason =
      node.type === "group"
        ? findInvalidGroupReason(audience, node)
        : findInvalidWidgetReason(audience, node);

    if (reason) {
      return reason;
    }
  }

  return undefined;
}

function findInvalidGroupReason(
  audience: DashboardAudience,
  node: LayoutGroupNode,
): string | undefined {
  return findInvalidNodeReason(audience, node.children);
}

function findInvalidWidgetReason(
  audience: DashboardAudience,
  node: LayoutWidgetNode,
): string | undefined {
  const widget = widgetRegistry[node.widgetId];

  if (!widget) {
    return `Missing widget "${node.widgetId}".`;
  }

  if (widget.supportedAudiences && !widget.supportedAudiences.includes(audience)) {
    return `Widget "${node.widgetId}" is not available for ${audience}.`;
  }

  return undefined;
}
