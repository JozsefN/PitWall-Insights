import { useMemo } from "react";
import {
  useReviewQuery,
  useSessionReview,
} from "../../../features/session-review/review-query";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import { requestedReviewGroups } from "../../review/review-specs";
import type { TrackMapLayer } from "../models";

export function useCircuitConditions(
  layer: TrackMapLayer,
  contextId?: string,
  lookbackTimeMs?: number,
) {
  const { selectedLayout } = useSessionWorkspace();
  const dashboardReview = useSessionReview();
  const group = layer === "weather" || layer === "flags" ? layer : undefined;
  const sharedGroup =
    group &&
    lookbackTimeMs == null &&
    selectedLayout &&
    requestedReviewGroups(selectedLayout.config).includes(group);
  const request = useReviewQuery(
    group ? [group] : [],
    [],
    Boolean(group && !sharedGroup),
    lookbackTimeMs == null ? undefined : { as_of_ms: lookbackTimeMs },
  );
  const surfaceRequest = useReviewQuery(
    ["surface"],
    [],
    Boolean(contextId && (layer === "surface" || layer === "flags")),
    { context_id: contextId, as_of_ms: lookbackTimeMs },
  );
  const review = sharedGroup ? dashboardReview : request;
  const surface = surfaceRequest.data?.groups.surface;
  const weather =
    layer === "weather" ? review.data?.groups.weather?.current : undefined;
  const flags = layer === "flags" ? review.data?.groups.flags : undefined;
  const overlay = useMemo(
    () => ({ layer, weather, flags, surface }),
    [layer, weather, flags, surface],
  );

  let status: string | undefined;
  if (group && !review.data) {
    status = review.isError
      ? "Conditions could not be loaded. Switch layers to retry."
      : "Loading circuit conditions…";
  } else if (layer === "surface" && !surface) {
    if (!contextId) {
      status =
        "Add a registered track profile in panel settings to show surveyed widths, runoff and recovery access.";
    } else {
      status = surfaceRequest.isError
        ? "The registered profile could not be loaded for this session."
        : "Loading registered circuit geometry…";
    }
  }
  return {
    overlay,
    asOfMs: group ? review.data?.as_of_ms : undefined,
    isFetching: review.isFetching,
    status,
  };
}
