import type { ComponentType } from "react";
import { ReviewWidget } from "./ReviewWidgets";
import { reviewPanels } from "./review-specs";
import type { ReviewPanelId } from "./review-specs";

export const reviewComponents = Object.fromEntries(
  (Object.keys(reviewPanels) as ReviewPanelId[]).map((panelId) => [
    panelId,
    function SessionReviewPanel({
      options,
    }: {
      options?: Record<string, unknown>;
    }) {
      return <ReviewWidget panelId={panelId} options={options} />;
    },
  ]),
) as Record<
  ReviewPanelId,
  ComponentType<{ options?: Record<string, unknown> }>
>;
