import {
  dashboardGrid,
  fitWidgetSize,
  widgetCatalog,
  widgetSizeError,
} from "../../widgets/registry/widget.catalog.ts";
import type {
  DashboardAudience,
  DashboardConfig,
  GridPlacement,
  LayoutRecord,
  LayoutWidgetNode,
  SectionLayoutNode,
  SessionKind,
  WidgetId,
} from "../../widgets/registry/widget.types";
import {
  sessionKindLabel,
  sessionKinds,
  supportedSessionKinds,
  widgetBlockReason,
} from "./compatibility.ts";

export const GRID_COLUMNS = dashboardGrid.columns;
export const GRID_ROW_HEIGHT = dashboardGrid.rowHeight;
export const GRID_GAP = dashboardGrid.gap;
export type EditorWidget = LayoutWidgetNode & {
  instanceId: string;
  placement: GridPlacement;
};
export type EditorSection = {
  id: string;
  title: string;
  description?: string;
  widgets: EditorWidget[];
};
export type EditorDraft = {
  name: string;
  description: string;
  audience: DashboardAudience;
  enabledAudiences?: DashboardAudience[];
  sessionKind?: SessionKind;
  sections: EditorSection[];
};

export function emptyDraft(
  audience: DashboardAudience,
  sessionKind?: SessionKind,
): EditorDraft {
  return {
    name: "",
    description: "",
    audience,
    sessionKind,
    sections: [{ id: crypto.randomUUID(), title: "", widgets: [] }],
  };
}

export function overlaps(a: GridPlacement, b: GridPlacement): boolean {
  return (
    a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y
  );
}

export function validPlacement(box: GridPlacement): boolean {
  return (
    Object.values(box).every(Number.isInteger) &&
    box.x >= 0 &&
    box.y >= 0 &&
    box.w >= 2 &&
    box.w <= 12 &&
    box.h >= 3 &&
    box.h <= 20 &&
    box.x + box.w <= 12 &&
    box.y + box.h <= 200
  );
}

export function canPlace(
  widgets: EditorWidget[],
  id: string,
  box: GridPlacement,
): boolean {
  const current = widgets.find((widget) => widget.instanceId === id);
  return (
    validPlacement(box) &&
    (!current || !widgetSizeError(current.widgetId, box)) &&
    widgets.every(
      (widget) => widget.instanceId === id || !overlaps(widget.placement, box),
    )
  );
}

// Resize from the fixed top-left corner. Keep untouched axes fixed and stop at
// the closest legal size in the requested direction, including nearby panels.
export function clampResize(
  widgets: EditorWidget[],
  widget: EditorWidget,
  requested: Pick<GridPlacement, "w" | "h">,
): GridPlacement {
  const original = widget.placement;
  if (![requested.w, requested.h].every(Number.isFinite)) return original;
  const size = widgetCatalog[widget.widgetId].sizing;
  const targetW = Math.max(
    size.minW,
    Math.min(size.maxW, GRID_COLUMNS - original.x, Math.round(requested.w)),
  );
  const targetH = Math.max(
    size.minH,
    Math.min(
      size.maxH,
      dashboardGrid.maxRows - original.y,
      Math.round(requested.h),
    ),
  );
  let closest = original;
  let distance = Infinity;
  for (
    let w = Math.min(original.w, targetW);
    w <= Math.max(original.w, targetW);
    w++
  ) {
    for (
      let h = Math.min(original.h, targetH);
      h <= Math.max(original.h, targetH);
      h++
    ) {
      const box = { ...original, w, h };
      const nextDistance = (w - targetW) ** 2 + (h - targetH) ** 2;
      if (
        nextDistance < distance &&
        canPlace(widgets, widget.instanceId, box)
      ) {
        closest = box;
        distance = nextDistance;
      }
    }
  }
  return closest;
}

export function findSpace(
  widgets: EditorWidget[],
  requested: Partial<GridPlacement> = {},
  widgetId?: WidgetId,
): GridPlacement | null {
  const fitted = widgetId ? fitWidgetSize(widgetId, requested) : null;
  const w = fitted?.w ?? Math.max(2, Math.min(12, requested.w ?? 6));
  const h = fitted?.h ?? Math.max(3, Math.min(20, requested.h ?? 5));
  const start = Math.max(0, Math.min(200 - h, requested.y ?? 0));
  const preferredX = Math.max(0, Math.min(12 - w, requested.x ?? 0));
  for (let y = start; y <= 200 - h; y++) {
    for (const x of [
      preferredX,
      ...Array.from({ length: 13 - w }, (_, index) => index),
    ]) {
      const box = { x, y, w, h };
      if (canPlace(widgets, "", box)) return box;
    }
  }
  return null;
}

export function newWidget(
  widgetId: WidgetId,
  placement: GridPlacement,
  options?: Record<string, unknown>,
): EditorWidget {
  return {
    type: "widget",
    widgetId,
    instanceId: crypto.randomUUID(),
    placement,
    options: structuredClone(options ?? {}),
  };
}

function flatten(node: SectionLayoutNode): LayoutWidgetNode[] {
  return node.type === "widget" ? [node] : node.children.flatMap(flatten);
}

// Translate legacy rows/columns to grid cells while retaining their relative arrangement.
function arrangeLegacy(
  node: SectionLayoutNode,
  x = 0,
  y = 0,
  width = 12,
): { nodes: LayoutWidgetNode[]; height: number } {
  if (node.type === "widget") {
    const height = Math.max(
      3,
      Math.min(
        20,
        node.minHeight
          ? Math.ceil(
              (node.minHeight + GRID_GAP) / (GRID_ROW_HEIGHT + GRID_GAP),
            )
          : node.height === "lg"
            ? 7
            : 5,
      ),
    );
    return {
      nodes: [{ ...node, placement: { x, y, w: width, h: height } }],
      height,
    };
  }
  if (node.direction === "column") {
    let height = 0;
    const nodes = node.children.flatMap((child) => {
      const result = arrangeLegacy(child, x, y + height, width);
      height += result.height;
      return result.nodes;
    });
    return { nodes, height };
  }
  const fractions = node.children.map((child) => {
    if (child.type !== "widget" || !child.width?.includes("/")) return null;
    const [numerator, denominator] = child.width.split("/").map(Number);
    return numerator / denominator;
  });
  const specified = fractions.reduce<number>(
    (total, fraction) => total + (fraction ?? 0),
    0,
  );
  const unspecified = fractions.filter((fraction) => fraction === null).length;
  const weights = fractions.map(
    (fraction) => fraction ?? Math.max(0.01, (1 - specified) / unspecified),
  );
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  let used = 0;
  const parts = node.children.map((child, index) => {
    const available = width - used;
    const childWidth =
      index === node.children.length - 1
        ? available
        : Math.max(2, Math.round((width * weights[index]) / total));
    const result = arrangeLegacy(child, x + used, y, childWidth);
    used += childWidth;
    return result;
  });
  return {
    nodes: parts.flatMap((part) => part.nodes),
    height: Math.max(0, ...parts.map((part) => part.height)),
  };
}

export function draftFromLayout(
  layout: LayoutRecord,
  copy = false,
  enforceSizing = true,
): EditorDraft {
  return {
    name: copy ? `${layout.name} copy`.slice(0, 160) : layout.name,
    description: layout.description ?? "",
    audience: layout.audience,
    enabledAudiences: layout.config.enabledAudiences,
    sessionKind: layout.config.sessionKind,
    sections: layout.config.sections.map((section) => {
      const widgets: EditorWidget[] = [];
      const nodes =
        section.layout.type === "group" && section.layout.grid
          ? flatten(section.layout)
          : arrangeLegacy(section.layout).nodes;
      for (const node of nodes) {
        const placement =
          node.placement &&
          canPlace(widgets, "", node.placement) &&
          (!enforceSizing || !widgetSizeError(node.widgetId, node.placement))
            ? { ...node.placement }
            : findSpace(
                widgets,
                {
                  w: node.placement?.w ?? (node.width === "full" ? 12 : 6),
                  h: node.placement?.h ?? (node.height === "lg" ? 7 : 5),
                },
                enforceSizing ? node.widgetId : undefined,
              );
        if (!placement)
          throw new Error("This layout exceeds the editor's 200-row limit.");
        widgets.push({
          ...structuredClone(node),
          instanceId:
            (copy ? undefined : node.instanceId) ?? crypto.randomUUID(),
          placement,
        });
      }
      return {
        id: section.id,
        title: section.title ?? "",
        description: section.description,
        widgets,
      };
    }),
  };
}

export function draftToConfig(draft: EditorDraft, id: string): DashboardConfig {
  return {
    id,
    enabledAudiences: draft.enabledAudiences,
    sessionKind: draft.sessionKind,
    title: draft.name.trim(),
    subtitle: draft.description.trim(),
    sections: draft.sections.map((section) => ({
      id: section.id,
      title: section.title || undefined,
      description: section.description,
      layout: {
        type: "group",
        direction: "row",
        gap: GRID_GAP,
        grid: { columns: GRID_COLUMNS, rowHeight: GRID_ROW_HEIGHT },
        children: section.widgets.map((widget) => ({
          type: "widget",
          widgetId: widget.widgetId,
          instanceId: widget.instanceId,
          placement: { ...widget.placement },
          options: structuredClone(widget.options ?? {}),
        })),
      },
    })),
  };
}

export function draftCompatibilityError(draft: EditorDraft): string | null {
  const kinds = draft.sessionKind ? [draft.sessionKind] : sessionKinds;
  for (const section of draft.sections)
    for (const widget of section.widgets) {
      const reason = widgetBlockReason(
        widget.widgetId,
        draft.enabledAudiences ?? [draft.audience],
        kinds,
      );
      if (reason)
        return (
          reason +
          (draft.sessionKind
            ? ` Current target: ${sessionKindLabel[draft.sessionKind]}.`
            : "")
        );
    }
  if (
    !supportedSessionKinds(
      draft.sections.flatMap((section) =>
        section.widgets.map((widget) => widget.widgetId),
      ),
      draft.sessionKind,
    ).length
  )
    return "None of the session types supports every panel in this layout. Remove the conflicting panel or change the session target.";
  return null;
}

export function draftError(draft: EditorDraft): string | null {
  const incompatibility = draftCompatibilityError(draft);
  if (incompatibility) return incompatibility;
  for (const section of draft.sections)
    for (const widget of section.widgets) {
      const sizeError = widgetSizeError(widget.widgetId, widget.placement);
      if (sizeError) return sizeError;
    }
  if (!draft.name.trim()) return "Give your layout a name.";
  if (
    !draft.sections.length ||
    draft.sections.some((section) => !section.widgets.length)
  )
    return "Add a widget to every group, or remove empty groups.";
  if (draft.sections.flatMap((section) => section.widgets).length > 100)
    return "A layout supports at most 100 widgets.";
  if (
    draft.sections.some((section) =>
      section.widgets.some(
        (widget) =>
          !canPlace(section.widgets, widget.instanceId, widget.placement),
      ),
    )
  )
    return "Widgets must fit inside the grid without overlapping.";
  return null;
}
