import type { SessionWorkspaceMode } from "../../widgets/registry/widget.types";

export type LapSelection = "all" | number;

export type SessionWorkspaceSearchState = {
  mode: SessionWorkspaceMode;
  layoutId: string | null;
  driverIds: string[];
  lap: LapSelection;
};

export const DEFAULT_SESSION_WORKSPACE_STATE: SessionWorkspaceSearchState = {
  mode: "lookback",
  layoutId: null,
  driverIds: [],
  lap: "all",
};

export function parseSessionWorkspaceSearchParams(
  searchParams: URLSearchParams,
): SessionWorkspaceSearchState {
  const mode = searchParams.get("mode") === "simulation" ? "simulation" : "lookback";
  const layoutId = searchParams.get("layout");
  const drivers = searchParams.get("drivers");
  const lapParam = searchParams.get("lap");
  const lapValue = Number(lapParam);

  return {
    mode,
    layoutId: layoutId && layoutId.trim() ? layoutId : null,
    driverIds: drivers
      ? Array.from(
          new Set(
            drivers
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
          ),
        )
      : [],
    lap:
      lapParam && Number.isInteger(lapValue) && lapValue > 0
        ? lapValue
        : "all",
  };
}

export function buildSessionWorkspaceSearchParams(
  state: SessionWorkspaceSearchState,
): URLSearchParams {
  const params = new URLSearchParams();

  params.set("mode", state.mode);

  if (state.layoutId) {
    params.set("layout", state.layoutId);
  }

  if (state.driverIds.length > 0) {
    params.set("drivers", state.driverIds.join(","));
  }

  params.set("lap", state.lap === "all" ? "all" : String(state.lap));

  return params;
}

export function buildSessionWorkspaceHref(
  sessionId: string,
  state: SessionWorkspaceSearchState,
): string {
  const params = buildSessionWorkspaceSearchParams(state).toString();
  return params ? `/sessions/${sessionId}?${params}` : `/sessions/${sessionId}`;
}
