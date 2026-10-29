import manifest from "../../../../shared/dashboard-widgets.json" with { type: "json" };
import type { GridPlacement, WidgetId, WidgetPolicy } from "./widget.types";

export const dashboardGrid = manifest.grid;
// Shared, version-controlled contract consumed by the API validator as well.
export const widgetCatalog = manifest.widgets as Record<WidgetId, WidgetPolicy>;

export function widgetSizeError(
  id: WidgetId,
  box: GridPlacement,
): string | null {
  const policy = widgetCatalog[id];
  if (!policy) return "Unknown widget.";
  const size = policy.sizing;
  if (
    box.w < size.minW ||
    box.h < size.minH ||
    box.w > size.maxW ||
    box.h > size.maxH
  )
    return `${policy.title} needs at least ${size.minW} columns × ${size.minH} rows (maximum ${size.maxW} × ${size.maxH}).`;
  const width =
    box.w *
      ((dashboardGrid.designWidth + dashboardGrid.gap) /
        dashboardGrid.columns) -
    dashboardGrid.gap;
  const height =
    box.h * (dashboardGrid.rowHeight + dashboardGrid.gap) - dashboardGrid.gap;
  if (size.minAspect && width / height < size.minAspect)
    return `${policy.title} needs a wider shape (width at least ${size.minAspect} × height).`;
  if (size.maxAspect && width / height > size.maxAspect)
    return `${policy.title} needs a taller shape (width at most ${size.maxAspect} × height).`;
  return null;
}

export function fitWidgetSize(
  id: WidgetId,
  requested: Partial<GridPlacement> = {},
): { w: number; h: number } {
  const size = widgetCatalog[id].sizing;
  let w = Math.max(
    size.minW,
    Math.min(size.maxW, requested.w ?? size.defaultW),
  );
  let h = Math.max(
    size.minH,
    Math.min(size.maxH, requested.h ?? size.defaultH),
  );
  for (
    let attempts = 0;
    attempts < 40 && widgetSizeError(id, { x: 0, y: 0, w, h });
    attempts++
  ) {
    const aspect =
      (w *
        ((dashboardGrid.designWidth + dashboardGrid.gap) /
          dashboardGrid.columns) -
        dashboardGrid.gap) /
      (h * (dashboardGrid.rowHeight + dashboardGrid.gap) - dashboardGrid.gap);
    if (size.minAspect && aspect < size.minAspect) {
      if (w < size.maxW) w++;
      else if (h > size.minH) h--;
      else break;
    } else if (h < size.maxH) h++;
    else if (w > size.minW) w--;
    else break;
  }
  return { w, h };
}
