import {
  buildSessionWorkspaceHref,
  type SessionWorkspaceSearchState,
} from "./session-workspace.search";

const ACTIVE_SESSION_WORKSPACE_KEY = "pitwall.active-session-workspace";

export type StoredSessionWorkspace = {
  sessionId: string;
  state: SessionWorkspaceSearchState;
  updatedAt: string;
};

export function readStoredSessionWorkspace(): StoredSessionWorkspace | null {
  if (typeof window === "undefined") {
    return null;
  }

  const rawValue = window.localStorage.getItem(ACTIVE_SESSION_WORKSPACE_KEY);

  if (!rawValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawValue) as Partial<StoredSessionWorkspace>;

    if (
      typeof parsed.sessionId !== "string" ||
      !parsed.sessionId.trim() ||
      !parsed.state ||
      (parsed.state.mode !== "lookback" && parsed.state.mode !== "simulation")
    ) {
      return null;
    }

    return {
      sessionId: parsed.sessionId,
      state: {
        mode: parsed.state.mode,
        layoutId:
          typeof parsed.state.layoutId === "string" && parsed.state.layoutId.trim()
            ? parsed.state.layoutId
            : null,
        driverIds: Array.isArray(parsed.state.driverIds)
          ? parsed.state.driverIds.filter(
              (driverId): driverId is string =>
                typeof driverId === "string" && driverId.trim().length > 0,
            )
          : [],
        lap:
          parsed.state.lap === "all" ||
          (typeof parsed.state.lap === "number" &&
            Number.isInteger(parsed.state.lap) &&
            parsed.state.lap > 0)
            ? parsed.state.lap
            : "all",
      },
      updatedAt:
        typeof parsed.updatedAt === "string" && parsed.updatedAt.trim()
          ? parsed.updatedAt
          : new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

export function writeStoredSessionWorkspace(
  workspace: StoredSessionWorkspace,
) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    ACTIVE_SESSION_WORKSPACE_KEY,
    JSON.stringify(workspace),
  );
}

export function buildStoredSessionWorkspaceHref(
  workspace: StoredSessionWorkspace | null,
): string | null {
  if (!workspace) {
    return null;
  }

  return buildSessionWorkspaceHref(workspace.sessionId, workspace.state);
}
