import { widgetSizeError } from "../../widgets/registry/widget.catalog";
import type { LayoutDto } from "../../data/contracts/layouts.contracts";
import { builtinSessionLayouts } from "../../widgets/registry/dashboard.config";
import { widgetRegistry } from "../../widgets/registry/widget.registry";
import { layoutCompatibilityReason, layoutModes } from "./compatibility";
import { raceViewerLayoutId, recommendedLayoutId } from "./layout-guides";
import type {
  DashboardAudience,
  LayoutGroupNode,
  LayoutRecord,
  LayoutWidgetNode,
  SectionLayoutNode,
  SessionKind,
} from "../../widgets/registry/widget.types";

export type ResolvedLayoutRecord = LayoutRecord & {
  isValid: boolean;
  invalidReason?: string;
};

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
  favorites: string[] = [],
  kind?: SessionKind,
): ResolvedLayoutRecord[] {
  return resolveAllLayouts(userLayouts, favorites)
    .filter((layout) => layoutModes(layout).includes(audience))
    .map((layout) => checkLayoutInSession(layout, audience, kind))
    .sort(sortLayoutsForSession(audience, kind, favorites));
}

export function sortLayoutsForSession(audience: DashboardAudience, kind?: SessionKind, favorites: readonly string[] = []) {
  const recommended = recommendedLayoutId(audience, kind);
  return (a: LayoutRecord, b: LayoutRecord) =>
    Number(favorites.includes(b.id)) - Number(favorites.includes(a.id)) ||
    Number(b.id === recommended) - Number(a.id === recommended);
}

export function resolveAllLayouts(
  userLayouts: LayoutDto[] | undefined,
  favorites: string[] = [],
): ResolvedLayoutRecord[] {
  return [
    ...builtinSessionLayouts,
    ...(userLayouts ?? []).map(toUserLayoutRecord),
  ]
    .map((layout) => validateResolvedLayout(layout))
    .sort(
      (a, b) =>
        Number(favorites.includes(b.id)) - Number(favorites.includes(a.id)) ||
        Number(b.id === raceViewerLayoutId) - Number(a.id === raceViewerLayoutId),
    );
}

export function checkLayoutInSession(
  layout: ResolvedLayoutRecord,
  audience: DashboardAudience,
  kind?: SessionKind,
): ResolvedLayoutRecord {
  const reason =
    layoutCompatibilityReason(layout, audience, kind) ?? layout.invalidReason;
  return reason ? { ...layout, isValid: false, invalidReason: reason } : layout;
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
  const invalidReason = ![1, 2].includes(layout.schemaVersion)
    ? `Layout schema version ${layout.schemaVersion} is not supported.`
    : (layoutCompatibilityReason(layout, layout.audience) ??
      findInvalidNodeReason(
        layout.config.sections.flatMap((section) => [section.layout]),
      ));

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

function findInvalidNodeReason(nodes: SectionLayoutNode[]): string | undefined {
  for (const node of nodes) {
    const reason =
      node.type === "group"
        ? findInvalidGroupReason(node)
        : findInvalidWidgetReason(node);

    if (reason) {
      return reason;
    }
  }

  return undefined;
}

function findInvalidGroupReason(node: LayoutGroupNode): string | undefined {
  return findInvalidNodeReason(node.children);
}

function findInvalidWidgetReason(node: LayoutWidgetNode): string | undefined {
  const widget = widgetRegistry[node.widgetId];

  if (!widget || !widget.builderEnabled) {
    return `Missing widget "${node.widgetId}".`;
  }

  if (node.placement)
    return widgetSizeError(node.widgetId, node.placement) ?? undefined;
  return undefined;
}
