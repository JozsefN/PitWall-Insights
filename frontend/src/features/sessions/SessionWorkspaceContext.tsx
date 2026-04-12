/* eslint-disable react-refresh/only-export-components */
import type { PropsWithChildren } from "react";
import { createContext, useContext, useEffect, useState } from "react";
import type {
  EntryLapDto,
  SessionDto,
  SessionEntryDto,
  SessionTickDto,
} from "../../data/contracts/sessions.contracts";
import { useEntryLapsQuery } from "../../data/queries/sessions.queries";
import type { DashboardAudience, SessionWorkspaceMode } from "../../widgets/registry/widget.types";
import { findTickAtTime } from "./session-utils";
import type { ResolvedLayoutRecord } from "./session-layouts";
import type { LapSelection } from "./session-workspace.search";

type ReplayController = {
  ticks: SessionTickDto[];
  currentTimeMs: number;
  isPlaying: boolean;
  speedMultiplier: number;
  minTimeMs: number;
  maxTimeMs: number;
  currentTick: SessionTickDto | null;
  leaderEntry: SessionEntryDto | null;
  leaderLaps: EntryLapDto[];
  togglePlayback: () => void;
  setCurrentTimeMs: (value: number) => void;
  setSpeedMultiplier: (value: number) => void;
  resetPlayback: () => void;
};

type SessionWorkspaceContextValue = {
  sessionId: string;
  session: SessionDto;
  entries: SessionEntryDto[];
  mode: SessionWorkspaceMode;
  audience: DashboardAudience;
  selectedLayout: ResolvedLayoutRecord | null;
  selectedDriverIds: string[];
  selectedEntries: SessionEntryDto[];
  lapSelection: LapSelection;
  replay: ReplayController;
};

type SessionWorkspaceProviderProps = PropsWithChildren<{
  sessionId: string;
  session: SessionDto;
  entries: SessionEntryDto[];
  mode: SessionWorkspaceMode;
  audience: DashboardAudience;
  selectedLayout: ResolvedLayoutRecord | null;
  selectedDriverIds: string[];
  lapSelection: LapSelection;
  ticks?: SessionTickDto[];
}>;

const SessionWorkspaceContext = createContext<SessionWorkspaceContextValue | null>(null);

export function SessionWorkspaceProvider({
  children,
  sessionId,
  session,
  entries,
  mode,
  audience,
  selectedLayout,
  selectedDriverIds,
  lapSelection,
  ticks = [],
}: SessionWorkspaceProviderProps) {
  const [currentTimeMs, setCurrentTimeMsState] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speedMultiplier, setSpeedMultiplierState] = useState(1);
  const leaderEntry = pickLeaderEntry(entries);
  const leaderLapsQuery = useEntryLapsQuery(sessionId, leaderEntry?.id, mode === "simulation");
  const leaderLaps = leaderLapsQuery.data ?? [];

  useEffect(() => {
    if (mode !== "simulation" || !isPlaying || ticks.length === 0) {
      return;
    }

    const maxTimeMs = ticks[ticks.length - 1]?.session_time_ms ?? 0;
    const interval = window.setInterval(() => {
      setCurrentTimeMsState((current) => {
        const next = (current || ticks[0].session_time_ms) + 100 * speedMultiplier;

        if (next >= maxTimeMs) {
          setIsPlaying(false);
          return maxTimeMs;
        }

        return next;
      });
    }, 100);

    return () => {
      window.clearInterval(interval);
    };
  }, [isPlaying, mode, speedMultiplier, ticks]);

  const selectedEntries = entries.filter((entry) => selectedDriverIds.includes(entry.id));
  const minTimeMs = ticks[0]?.session_time_ms ?? 0;
  const maxTimeMs = ticks[ticks.length - 1]?.session_time_ms ?? 0;
  const effectiveCurrentTimeMs = currentTimeMs || minTimeMs;

  const value: SessionWorkspaceContextValue = {
    sessionId,
    session,
    entries,
    mode,
    audience,
    selectedLayout,
    selectedDriverIds,
    selectedEntries,
    lapSelection,
    replay: {
      ticks,
      currentTimeMs: effectiveCurrentTimeMs,
      isPlaying,
      speedMultiplier,
      minTimeMs,
      maxTimeMs,
      currentTick: findTickAtTime(ticks, effectiveCurrentTimeMs),
      leaderEntry,
      leaderLaps,
      togglePlayback: () => {
        if (ticks.length === 0) {
          return;
        }

        setIsPlaying((current) => !current);
      },
      setCurrentTimeMs: (value) => {
        setCurrentTimeMsState(Math.max(minTimeMs, Math.min(value, maxTimeMs)));
      },
      setSpeedMultiplier: (value) => {
        setSpeedMultiplierState(value);
      },
      resetPlayback: () => {
        setIsPlaying(false);
        setCurrentTimeMsState(minTimeMs);
      },
    },
  };

  return (
    <SessionWorkspaceContext.Provider value={value}>
      {children}
    </SessionWorkspaceContext.Provider>
  );
}

export function useSessionWorkspace() {
  const value = useContext(SessionWorkspaceContext);

  if (!value) {
    throw new Error("Session workspace context is not available.");
  }

  return value;
}

function pickLeaderEntry(entries: SessionEntryDto[]) {
  return [...entries].sort((left, right) => {
    const leftRank = left.result_position ?? Number.MAX_SAFE_INTEGER;
    const rightRank = right.result_position ?? Number.MAX_SAFE_INTEGER;

    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }

    return Number(left.car_number) - Number(right.car_number);
  })[0] ?? null;
}
