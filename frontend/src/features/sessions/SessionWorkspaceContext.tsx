/* eslint-disable react-refresh/only-export-components */
import type { PropsWithChildren } from "react";
import { createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import type {
  EntryLapDto,
  SessionDto,
  SessionEntryDto,
  SessionTickDto,
} from "../../data/contracts/sessions.contracts";
import { useEntryLapsQuery } from "../../data/queries/sessions.queries";
import type {
  DashboardAudience,
  SessionWorkspaceMode,
} from "../../widgets/registry/widget.types";
import type { ResolvedLayoutRecord } from "./session-layouts";
import type { LapSelection } from "./session-workspace.search";
import type { LapChoice } from "../session-review/contracts";
import { createReplayClock, type ReplayClock } from "./replay-clock";
import { formatReplayElapsed } from "./replay-timeline";
import { raceTime } from "../race-insights/presentation";

type ReplayController = {
  clock: ReplayClock;
  isPlaying: boolean;
  speedMultiplier: number;
  minTimeMs: number;
  maxTimeMs: number;
  leaderEntry: SessionEntryDto | null;
  leaderLaps: EntryLapDto[];
  togglePlayback: (canStart: boolean) => void;
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
  qualifyingLap: LapChoice | undefined;
  selectQualifyingLap: (choice: LapChoice) => void;
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

const SessionWorkspaceContext =
  createContext<SessionWorkspaceContextValue | null>(null);

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
  const [clock] = useState(createReplayClock);
  const [qualifyingSelection, setQualifyingSelection] = useState<{ sessionId: string; lap: LapChoice }>();
  const scope = JSON.stringify([
    sessionId,
    mode,
    selectedLayout?.isValid ? selectedLayout.id : null,
    [...selectedDriverIds].sort(),
  ]);
  const [playback, setPlayback] = useState({ scope, playing: false });
  const isPlaying = playback.scope === scope && playback.playing;
  if (playback.scope !== scope) setPlayback({ scope, playing: false });
  const [speedMultiplier, setSpeedMultiplierState] = useState(1);
  const leaderEntry = useMemo(() => pickLeaderEntry(entries), [entries]);
  const leaderLapsQuery = useEntryLapsQuery(
    sessionId,
    leaderEntry?.id,
    mode === "simulation",
  );
  const leaderLaps = leaderLapsQuery.data ?? [];
  const minTimeMs = ticks[0]?.session_time_ms ?? 0;
  const maxTimeMs = ticks[ticks.length - 1]?.session_time_ms ?? 0;

  useEffect(() => {
    if (mode !== "simulation" || !isPlaying || maxTimeMs <= minTimeMs) {
      return;
    }

    let published = clock.frame.getTime();
    let base = published ?? minTimeMs;
    let started = performance.now();
    let lastFrame = started;
    let lastReadout = started;
    let lastReview = started;
    let handle: number;
    function frame(now: number) {
      if (clock.frame.getTime() !== published) {
        published = clock.frame.getTime();
        base = published ?? minTimeMs;
        started = now;
        lastReview = now;
      }
      const next = Math.min(maxTimeMs, Math.round(base + Math.max(0, now - started) * speedMultiplier));
      const finished = next === maxTimeMs;
      if (now - lastFrame >= 32 || finished) {
        published = next;
        clock.frame.setTime(next);
        lastFrame = now;
      }
      if (now - lastReadout >= 240 || finished) {
        clock.readout.setTime(next);
        lastReadout = now;
      }
      if (now - lastReview >= 2000 || finished) {
        clock.review.setTime(next);
        lastReview = now;
      }
      if (finished) setPlayback({ scope, playing: false });
      else handle = requestAnimationFrame(frame);
    }
    handle = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(handle);
  }, [clock, isPlaying, maxTimeMs, minTimeMs, mode, scope, speedMultiplier]);

  const selectedEntries = useMemo(
    () => entries.filter((entry) => selectedDriverIds.includes(entry.id)),
    [entries, selectedDriverIds],
  );
  function seek(timeMs: number) {
    const next = Math.max(minTimeMs, Math.min(timeMs, maxTimeMs));
    clock.frame.setTime(next);
    clock.readout.setTime(next);
    clock.review.setTime(next);
  }

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
    qualifyingLap: qualifyingSelection?.sessionId === sessionId ? qualifyingSelection.lap : undefined,
    selectQualifyingLap: (lap) => setQualifyingSelection({ sessionId, lap }),
    replay: {
      clock,
      isPlaying,
      speedMultiplier,
      minTimeMs,
      maxTimeMs,
      leaderEntry,
      leaderLaps,
      togglePlayback: (canStart) => {
        if (
          !isPlaying &&
          (!canStart || mode !== "simulation" || maxTimeMs <= minTimeMs)
        )
          return;
        if (isPlaying) seek(clock.frame.getTime() ?? minTimeMs);
        setPlayback({ scope, playing: !isPlaying });
      },
      setCurrentTimeMs: seek,
      setSpeedMultiplier: (value) => {
        setSpeedMultiplierState(value);
      },
      resetPlayback: () => {
        setPlayback({ scope, playing: false });
        seek(minTimeMs);
      },
    },
  };

  return (
    <SessionWorkspaceContext.Provider value={value}>
      {children}
    </SessionWorkspaceContext.Provider>
  );
}

export function useReplayTime(channel: keyof ReplayClock = "readout") {
  const { replay } = useSessionWorkspace();
  const signal = replay.clock[channel];
  return useSyncExternalStore(signal.subscribe, signal.getTime) ?? replay.minTimeMs;
}

export function useSessionWorkspace() {
  const value = useContext(SessionWorkspaceContext);

  if (!value) {
    throw new Error("Session workspace context is not available.");
  }

  return value;
}

export function useSessionTimeLabel() {
  const { mode, replay } = useSessionWorkspace();
  return (timeMs: number) => mode === "simulation" ? formatReplayElapsed(timeMs, replay.minTimeMs) : raceTime(timeMs);
}

function pickLeaderEntry(entries: SessionEntryDto[]) {
  return (
    [...entries].sort((left, right) => {
      const leftRank = left.result_position ?? Number.MAX_SAFE_INTEGER;
      const rightRank = right.result_position ?? Number.MAX_SAFE_INTEGER;

      if (leftRank !== rightRank) {
        return leftRank - rightRank;
      }

      return Number(left.car_number) - Number(right.car_number);
    })[0] ?? null
  );
}
