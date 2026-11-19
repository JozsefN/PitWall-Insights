import type { CSSProperties } from "react";
import type { SessionEntryDto } from "../../data/contracts/sessions.contracts";
import { useReplayTime, useSessionWorkspace } from "./SessionWorkspaceContext";
import { useReplayStartBlock } from "./use-replay-start-block";
import { formatReplayElapsed } from "./replay-timeline";
import type { SessionWorkspaceSearchState } from "./session-workspace.search";
import {
  getEntryDisplayName,
  getEntryAccent,
  orderByStartingGrid,
} from "./session-utils";

const REPLAY_SPEEDS = [1, 2, 3, 5, 10];

export function LookbackControls({
  entries,
  selectedDriverIds,
  lapOptions,
  isLapLoading,
  currentLap,
  onToggleDriver,
  onSelectAllDrivers,
  onClearDrivers,
  onLapChange,
}: {
  entries: SessionEntryDto[];
  selectedDriverIds: string[];
  lapOptions: number[];
  isLapLoading: boolean;
  currentLap: SessionWorkspaceSearchState["lap"];
  onToggleDriver: (driverId: string) => void;
  onSelectAllDrivers: () => void;
  onClearDrivers: () => void;
  onLapChange: (lap: SessionWorkspaceSearchState["lap"]) => void;
}) {
  return (
    <section className="sessions-controls">
      <div className="sessions-subheading">
        <h2>Lookback controls</h2>
        <p>
          <strong>{selectedDriverIds.length}</strong> of{" "}
          <strong>{entries.length}</strong> drivers selected. Widgets decide
          whether they use all laps or require one lap.
        </p>
      </div>

      <div className="sessions-lookback-controls-grid">
        <DriverSelectionControl
          entries={entries}
          selectedDriverIds={selectedDriverIds}
          onToggleDriver={onToggleDriver}
          onSelectAllDrivers={onSelectAllDrivers}
          onClearDrivers={onClearDrivers}
        />

        <div className="sessions-control-stack">
          <span className="sessions-control-label">Lap scope</span>
          <div className="sessions-lap-strip">
            <button
              type="button"
              className={`sessions-lap-chip${currentLap === "all" ? " is-active" : ""}`}
              aria-pressed={currentLap === "all"}
              onClick={() => onLapChange("all")}
            >
              All laps
            </button>

            {isLapLoading ? (
              <span className="sessions-inline-loading">
                Loading lap list...
              </span>
            ) : null}

            {lapOptions.map((lap) => (
              <button
                key={lap}
                type="button"
                className={`sessions-lap-chip${currentLap === lap ? " is-active" : ""}`}
                aria-pressed={currentLap === lap}
                onClick={() => onLapChange(lap)}
              >
                Lap {lap}
              </button>
            ))}
          </div>
        </div>
      </div>

      {selectedDriverIds.length > 4 ? (
        <div className="sessions-empty-state">
          Large comparisons are allowed, but some widgets will feel heavier once
          you move beyond four drivers.
        </div>
      ) : null}
    </section>
  );
}

function DriverSelectionControl({
  entries,
  selectedDriverIds,
  onToggleDriver,
  onSelectAllDrivers,
  onClearDrivers,
}: {
  entries: SessionEntryDto[];
  selectedDriverIds: string[];
  onToggleDriver: (driverId: string) => void;
  onSelectAllDrivers: () => void;
  onClearDrivers: () => void;
}) {
  return (
    <div className="sessions-control-stack">
      <div className="sessions-driver-toolbar">
        <span className="sessions-control-label">Drivers</span>
        <div className="sessions-driver-actions">
          <button
            type="button"
            className="sessions-mini-action"
            onClick={onSelectAllDrivers}
          >
            All
          </button>
          <button
            type="button"
            className="sessions-mini-action"
            onClick={onClearDrivers}
          >
            Clear
          </button>
        </div>
      </div>

      <div className="sessions-driver-strip">
        {entries.map((entry, index) => {
          const isSelected = selectedDriverIds.includes(entry.id);

          return (
            <button
              key={entry.id}
              type="button"
              className={`sessions-driver-chip${isSelected ? " is-active" : ""}`}
              style={
                {
                  "--driver-color": getEntryAccent(entry, index),
                } as CSSProperties
              }
              aria-pressed={isSelected}
              onClick={() => onToggleDriver(entry.id)}
            >
              <span className="sessions-driver-chip__number" aria-hidden="true">
                {entry.car_number}
              </span>
              <strong>{entry.driver_name || getEntryDisplayName(entry)}</strong>
              <small>{entry.team_name ?? `Car ${entry.car_number}`}</small>
              {isSelected ? (
                <span
                  className="sessions-driver-chip__selected"
                  aria-hidden="true"
                >
                  ✓
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function SimulationReplayBar({
  entries,
  selectedDriverIds,
  timelineLoading,
  timelineError,
  onToggleDriver,
  onSelectAllDrivers,
  onClearDrivers,
}: {
  entries: SessionEntryDto[];
  selectedDriverIds: string[];
  timelineLoading: boolean;
  timelineError: boolean;
  onToggleDriver: (driverId: string) => void;
  onSelectAllDrivers: () => void;
  onClearDrivers: () => void;
}) {
  const workspace = useSessionWorkspace();
  const replay = workspace.replay;
  const timeMs = useReplayTime();
  const startBlock = useReplayStartBlock(timelineLoading, timelineError);
  const cannotStart = !replay.isPlaying && Boolean(startBlock);
  const timelineDuration = replay.maxTimeMs - replay.minTimeMs;
  const elapsed = timeMs - replay.minTimeMs;
  const elapsedLabel = formatReplayElapsed(timeMs, replay.minTimeMs);
  const replayProgress =
    timelineDuration > 0
      ? Math.min(100, Math.max(0, (100 * elapsed) / timelineDuration))
      : 0;
  const currentLap =
    replay.leaderLaps.find((lap) => {
      const start = lap.lap_start_time_ms ?? 0;
      const end = lap.lap_end_time_ms ?? Number.MAX_SAFE_INTEGER;
      return timeMs >= start && timeMs < end;
    }) ?? null;

  return (
    <section className="sessions-controls sessions-controls--simulation">
      <div className="sessions-subheading">
        <h2>Replay controls</h2>
        <p>
          <strong>{selectedDriverIds.length}</strong> of{" "}
          <strong>{entries.length}</strong> drivers selected.
        </p>
      </div>

      <DriverSelectionControl
        entries={orderByStartingGrid(entries)}
        selectedDriverIds={selectedDriverIds}
        onToggleDriver={onToggleDriver}
        onSelectAllDrivers={onSelectAllDrivers}
        onClearDrivers={onClearDrivers}
      />

      <div className="sessions-replay-console">
        <div className="sessions-replay-summary">
          <label className="sessions-replay-jump">
            <span>Jump to lap</span>
            <select
              aria-label="Jump to lap"
              value={currentLap?.id ?? ""}
              onChange={(event) => {
                const lap = replay.leaderLaps.find(
                  ({ id }) => id === event.target.value,
                );
                if (lap?.lap_start_time_ms != null)
                  replay.setCurrentTimeMs(lap.lap_start_time_ms);
              }}
              disabled={!replay.leaderLaps.length}
            >
              <option value="" disabled>
                Choose lap
              </option>
              {replay.leaderLaps
                .filter((lap) => lap.lap_start_time_ms != null)
                .map((lap) => (
                  <option key={lap.id} value={lap.id}>
                    Lap {lap.lap_number}
                  </option>
                ))}
            </select>
          </label>
          <div className="sessions-replay-clock">
            <span>Elapsed</span>
            <strong aria-label="Elapsed replay time">{elapsedLabel}</strong>
          </div>
        </div>

        <div className="sessions-replay-timeline">
          <input
            type="range"
            aria-label="Replay time"
            aria-valuetext={elapsedLabel}
            min={replay.minTimeMs}
            max={replay.maxTimeMs || replay.minTimeMs + 1}
            value={timeMs}
            style={{ "--replay-fill": `${replayProgress}%` } as CSSProperties}
            onChange={(event) =>
              replay.setCurrentTimeMs(Number(event.target.value))
            }
          />
        </div>

        <div className="sessions-replay-actions">
          <button
            type="button"
            className="button-primary"
            disabled={cannotStart}
            aria-describedby={cannotStart ? "replay-start-status" : undefined}
            onClick={() => replay.togglePlayback(!startBlock)}
          >
            {replay.isPlaying ? "Pause" : "Start"}
          </button>
          <button
            type="button"
            className="button-secondary"
            onClick={replay.resetPlayback}
          >
            Reset
          </button>

          <div className="sessions-speed-list">
            {REPLAY_SPEEDS.map((speed) => (
              <button
                key={speed}
                type="button"
                className={`sessions-speed-chip${replay.speedMultiplier === speed ? " is-active" : ""}`}
                aria-pressed={replay.speedMultiplier === speed}
                onClick={() => replay.setSpeedMultiplier(speed)}
              >
                {speed}x
              </button>
            ))}
          </div>
        </div>
        <p
          id="replay-start-status"
          className="sessions-replay-start-status"
          role="status"
        >
          {cannotStart ? startBlock : ""}
        </p>
      </div>
    </section>
  );
}
