import type { ComponentType } from "react";
import { InsightWidget } from "./InsightWidgets";
import { insightPanels } from "./panel-specs";
import type { InsightPanelId } from "./panel-specs";

export const insightComponents = Object.fromEntries(
  (Object.keys(insightPanels) as InsightPanelId[]).map((panelId) => [
    panelId,
    function RaceInsightPanel({
      options,
    }: {
      options?: Record<string, unknown>;
    }) {
      return <InsightWidget panelId={panelId} options={options} />;
    },
  ]),
) as Record<
  InsightPanelId,
  ComponentType<{ options?: Record<string, unknown> }>
>;
