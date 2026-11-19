import { createContext, useContext } from "react";
import type { TelemetryKind } from "../../data/contracts/telemetry-materialization.contracts";
import type {
  useWorkspaceCarTelemetryResource,
  useWorkspaceEntryLapsResource,
  useWorkspacePositionTelemetryResource,
} from "./session-data.hooks";

type ReplayData = {
  car: ReturnType<typeof useWorkspaceCarTelemetryResource>;
  position: ReturnType<typeof useWorkspacePositionTelemetryResource>;
  laps: ReturnType<typeof useWorkspaceEntryLapsResource>;
  needsDrivers: boolean;
  needsCar: boolean;
  needsPosition: boolean;
  needsLaps: boolean;
  needsInsights: boolean;
  needsReview: boolean;
  insightTelemetry: TelemetryKind[];
};

export const WorkspaceReplayDataContext = createContext<ReplayData | null>(
  null,
);

export function useWorkspaceReplayData() {
  const data = useContext(WorkspaceReplayDataContext);
  if (!data) throw new Error("Workspace replay data is unavailable.");
  return data;
}
