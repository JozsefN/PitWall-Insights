import type { PropsWithChildren } from "react";
import {
  insightPanels,
  insightReplayTelemetry,
  type InsightPanelId,
} from "../../widgets/insights/panel-specs";
import { requestedReviewGroups } from "../../widgets/review/review-specs";
import { widgetIds } from "../dashboards/compatibility";
import { RaceEstimationProvider } from "../race-insights/RaceEstimationProvider";
import { ReviewProvider } from "../session-review/ReviewProvider";
import { useSessionWorkspace } from "./SessionWorkspaceContext";
import { sampledSessionTelemetry } from "./replay-timeline";
import {
  useWorkspaceCarTelemetryResource,
  useWorkspaceEntryLapsResource,
  useWorkspacePositionTelemetryResource,
} from "./session-data.hooks";
import { WorkspaceReplayDataContext } from "./workspace-replay-data";
import { StrategyReplayProvider } from "../replay-strategy/StrategyReplayProvider";
import { replayStrategyPanelIds } from "../replay-strategy/strategy-replay-context";

export function WorkspaceDashboardDataProvider({
  children,
}: PropsWithChildren) {
  const workspace = useSessionWorkspace();
  const layout = workspace.selectedLayout;
  const config = layout?.isValid ? layout.config : undefined;
  const ids = config ? widgetIds(config) : [];
  const reviewGroups = config ? requestedReviewGroups(config) : [];
  const replay = workspace.mode === "simulation";
  const insights = ids.filter(
    (id): id is InsightPanelId => id in insightPanels,
  );
  const insightTelemetry = [
    ...new Set(insights.flatMap((id) => insightReplayTelemetry[id] ?? [])),
  ];
  const needsCar = replay && ids.includes("replay-driver-cards");
  const needsPosition = replay && ids.includes("replay-track-map");
  const needsLaps = replay && (needsPosition || ids.some((id) => ["stint-analysis", "tyre-timeline", "position-history", "replay-timing-board"].includes(id)));
  const needsDrivers =
    needsCar || needsLaps || insightTelemetry.length > 0;
  const selected = workspace.selectedDriverIds;
  const { minTimeMs, maxTimeMs } = workspace.replay;
  const hasTimeline = maxTimeMs > minTimeMs;
  const sample = sampledSessionTelemetry(minTimeMs, maxTimeMs);
  const car = useWorkspaceCarTelemetryResource({
    ...sample,
    entryIds: needsCar ? selected : [],
    enabled: needsCar && hasTimeline,
  });
  const position = useWorkspacePositionTelemetryResource({
    ...sample,
    entryIds: needsPosition ? selected : [],
    enabled: needsPosition && hasTimeline,
  });
  const laps = useWorkspaceEntryLapsResource({
    entryIds: needsLaps ? selected : [],
    enabled: needsLaps,
  });

  return (
    <WorkspaceReplayDataContext.Provider
      value={{
        car,
        position,
        laps,
        needsDrivers,
        needsCar,
        needsPosition,
        needsLaps,
        needsInsights: insights.length > 0,
        needsReview: reviewGroups.length > 0,
        insightTelemetry,
      }}
    >
      <RaceEstimationProvider enabled={insights.length > 0}>
        <ReviewProvider groups={reviewGroups}>
          <StrategyReplayProvider enabled={replay && replayStrategyPanelIds.some((id) => ids.includes(id))}>
            {children}
          </StrategyReplayProvider>
        </ReviewProvider>
      </RaceEstimationProvider>
    </WorkspaceReplayDataContext.Provider>
  );
}
