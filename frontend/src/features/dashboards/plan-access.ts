import type { Plan } from "../../data/queries/billing.queries";
import type { LayoutDto } from "../../data/contracts/layouts.contracts";
import { widgetCatalog } from "../../widgets/registry/widget.catalog";
import type { LayoutRecord } from "../../widgets/registry/widget.types";
import { widgetInstances } from "./compatibility";

export function layoutPlanRestriction(layout: LayoutRecord, plan?: Plan, layouts?: LayoutDto[]): string | undefined {
  const panels = widgetInstances(layout.config);
  if (panels.some(id => widgetCatalog[id]?.accessTier > (plan?.level ?? 0)))
    return "Requires Analyst or Pro.";
  if (layout.source === "builtin" || !plan) return;
  if (panels.length > plan.panels_per_layout)
    return `${plan.name} allows ${plan.panels_per_layout} panels per saved layout.`;
  if (layouts && layouts.length > plan.saved_layouts) {
    const available = [...layouts]
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id))
      .slice(0, plan.saved_layouts);
    if (!available.some(item => item.id === layout.storageId))
      return `${plan.name} allows ${plan.saved_layouts} saved layouts. Free a slot or change plan.`;
  }
}
