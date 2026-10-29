import type {
  DashboardAudience,
  SessionWorkspaceMode,
} from "../../widgets/registry/widget.types";

export {
  getResolvedLayoutById,
  resolveWorkspaceLayouts,
  toUserLayoutRecord,
} from "../dashboards/layout-catalog";
export type { ResolvedLayoutRecord } from "../dashboards/layout-catalog";

export function getAudienceForMode(
  mode: SessionWorkspaceMode,
): DashboardAudience {
  return mode === "simulation" ? "live-race" : "session-lookback";
}
