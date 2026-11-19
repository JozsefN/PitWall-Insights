import { useRaceEstimationResource } from "../race-insights/race-estimation-context";
import { useSessionReview } from "../session-review/review-query";
import { useSessionWorkspace } from "./SessionWorkspaceContext";
import { useWorkspaceReplayData } from "./workspace-replay-data";

export function useReplayStartBlock(
  timelineLoading: boolean,
  timelineError: boolean,
) {
  const { replay, selectedLayout, selectedDriverIds, entries } =
    useSessionWorkspace();
  const data = useWorkspaceReplayData();
  const analysis = useRaceEstimationResource();
  const review = useSessionReview();

  if (replay.maxTimeMs <= replay.minTimeMs) {
    if (timelineLoading) return "Loading the replay timeline…";
    if (timelineError)
      return "The replay timeline could not be loaded. Reload this workspace to retry.";
    return "This session has no playable replay timeline.";
  }
  if (!selectedLayout?.isValid)
    return "Choose a compatible replay layout to start.";
  if (!entries.length) return "This session has no driver entries to replay.";
  if (data.needsDrivers && !selectedDriverIds.length)
    return "Choose at least one driver to load this layout's data.";

  if (data.needsCar) {
    const blocked = telemetryBlock(data.car, "Car telemetry");
    if (blocked) return blocked;
  }
  if (data.needsPosition) {
    const blocked = telemetryBlock(data.position, "Position telemetry");
    if (blocked) return blocked;
  }
  if (data.needsLaps) {
    if (data.laps.isError)
      return "Lap data could not be loaded. Reload this workspace or choose other drivers.";
    if (data.laps.isLoading) return "Loading lap data for the selected layout…";
  }
  for (const kind of data.insightTelemetry) {
    const status = analysis.telemetryReadiness[kind];
    const label = kind === "car" ? "Car telemetry" : "Position telemetry";
    if (status.ready) continue;
    if (status.isError)
      return `${label} preparation failed. Try a different driver or layout.`;
    if (status.queueStalled)
      return `${label} is queued. Waiting for the background worker.`;
    return `Preparing ${label.toLowerCase()} for race analysis…`;
  }
  if (data.needsInsights) {
    const blocked = snapshotBlock(analysis.query, "race analysis");
    if (blocked) return blocked;
  }
  if (data.needsReview) return snapshotBlock(review, "session review");
}

function telemetryBlock(
  resource: {
    ready: boolean;
    isLoading: boolean;
    isError: boolean;
    queueStalled: boolean;
    entryIds: string[];
    dataByEntryId: Record<string, unknown[]>;
  },
  label: string,
) {
  if (resource.isError)
    return `${label} could not be loaded. Try a different driver or layout.`;
  if (resource.queueStalled && !resource.ready)
    return `${label} is queued. Waiting for the background worker.`;
  if (!resource.ready) return `Preparing ${label.toLowerCase()}…`;
  if (resource.isLoading)
    return `Loading ${label.toLowerCase()} samples into the replay…`;
  const missing = resource.entryIds.filter(
    (id) => !resource.dataByEntryId[id]?.length,
  );
  if (missing.length)
    return `${label} is missing for ${missing.length} driver${missing.length === 1 ? "" : "s"}. Try a different selection.`;
}

function snapshotBlock(
  query: { data?: unknown; isError: boolean; isPlaceholderData: boolean },
  label: string,
) {
  if (query.data && !query.isPlaceholderData) return undefined;
  if (query.isError)
    return `The ${label} could not be loaded. Retry in the panel or choose another layout.`;
  return `Loading the ${label} for this replay time…`;
}
