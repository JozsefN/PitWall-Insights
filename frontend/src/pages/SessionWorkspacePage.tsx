import { useQueries } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { PageContainer } from "../app/layout/PageContanier";
import { listEntryLaps } from "../data/api/sessions.api";
import type { SessionEntryDto } from "../data/contracts/sessions.contracts";
import { useLayoutsQuery } from "../data/queries/layouts.queries";
import { useSessionEntriesQuery, useSessionQuery, useSessionTicksQuery } from "../data/queries/sessions.queries";
import { useAuthSession } from "../features/auth/useAuthSession";
import { writeStoredSessionWorkspace } from "../features/sessions/session-resume";
import { SessionWorkspaceProvider, useSessionWorkspace } from "../features/sessions/SessionWorkspaceContext";
import { getAudienceForMode, getResolvedLayoutById, resolveWorkspaceLayouts } from "../features/sessions/session-layouts";
import {
  buildSessionWorkspaceSearchParams,
  parseSessionWorkspaceSearchParams,
  type SessionWorkspaceSearchState,
} from "../features/sessions/session-workspace.search";
import {
  formatDateTime,
  formatEventSessionLabel,
  formatLapTime,
  formatSessionClock,
  getEntryDisplayName,
} from "../features/sessions/session-utils";
import { DashboardRenderer } from "../widgets/shared/DashboardRenderer";
import "./sessions-page.css";

const REPLAY_SPEEDS = [1, 2, 3, 5, 10];

export function SessionWorkspacePage() {
  const { sessionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const sessionQuery = useSessionQuery(sessionId);
  const entriesQuery = useSessionEntriesQuery(sessionId);
  const authSession = useAuthSession();
  const searchState = parseSessionWorkspaceSearchParams(searchParams);
  const audience = getAudienceForMode(searchState.mode);
  const layoutsQuery = useLayoutsQuery(authSession.data?.authenticated === true);
  const resolvedLayouts = resolveWorkspaceLayouts(layoutsQuery.data, audience);
  const selectedLayout = getResolvedLayoutById(searchState.layoutId, resolvedLayouts);
  const ticksQuery = useSessionTicksQuery(sessionId, { limit: 50000 }, searchState.mode === "simulation");

  const entries = entriesQuery.data ?? [];
  const validDriverIds = searchState.driverIds.filter((driverId) =>
    entries.some((entry) => entry.id === driverId),
  );
  const validDriverIdsKey = validDriverIds.join(",");

  const lapQueries = useQueries({
    queries: validDriverIds.map((entryId) => ({
      queryKey: ["sessions", sessionId, "entries", entryId, "laps", "controls"],
      queryFn: () => listEntryLaps(sessionId as string, entryId),
      enabled: searchState.mode === "lookback" && validDriverIds.length > 0,
    })),
  });

  const lapOptions = Array.from(
    new Set(lapQueries.flatMap((query) => (query.data ?? []).map((lap) => lap.lap_number))),
  ).sort((left, right) => left - right);

  useEffect(() => {
    if (validDriverIds.length === searchState.driverIds.length) {
      return;
    }

    updateSearchState(searchState, setSearchParams, { driverIds: validDriverIds });
  }, [searchState, setSearchParams, validDriverIds]);

  useEffect(() => {
    if (!searchState.layoutId || selectedLayout || layoutsQuery.isLoading) {
      return;
    }

    updateSearchState(searchState, setSearchParams, { layoutId: null });
  }, [layoutsQuery.isLoading, searchState, selectedLayout, setSearchParams]);

  useEffect(() => {
    if (searchState.lap === "all" || lapOptions.includes(searchState.lap)) {
      return;
    }

    updateSearchState(searchState, setSearchParams, { lap: "all" });
  }, [lapOptions, searchState, setSearchParams]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    writeStoredSessionWorkspace({
      sessionId,
      state: {
        mode: searchState.mode,
        layoutId: selectedLayout?.id ?? null,
        driverIds: validDriverIdsKey ? validDriverIdsKey.split(",") : [],
        lap: searchState.lap,
      },
      updatedAt: new Date().toISOString(),
    });
  }, [
    searchState.lap,
    searchState.mode,
    selectedLayout?.id,
    sessionId,
    validDriverIdsKey,
  ]);

  if (!sessionId) {
    return (
      <PageContainer>
        <div className="sessions-empty-state sessions-empty-state--error">Session id is missing from the route.</div>
      </PageContainer>
    );
  }

  if (sessionQuery.isLoading || entriesQuery.isLoading) {
    return (
      <PageContainer>
        <div className="sessions-empty-state">Loading session workspace...</div>
      </PageContainer>
    );
  }

  if (sessionQuery.isError || entriesQuery.isError || !sessionQuery.data) {
    return (
      <PageContainer>
        <div className="sessions-empty-state sessions-empty-state--error">The session workspace could not be loaded.</div>
      </PageContainer>
    );
  }

  return (
    <PageContainer size="wide">
      <SessionWorkspaceProvider
        sessionId={sessionId}
        session={sessionQuery.data}
        entries={entries}
        mode={searchState.mode}
        audience={audience}
        selectedLayout={selectedLayout}
        selectedDriverIds={validDriverIds}
        lapSelection={searchState.lap}
        ticks={ticksQuery.data ?? []}
      >
        <div className="sessions-shell">
          <section className="surface-card sessions-workspace">
            <header className="sessions-workspace__hero">
              <div className="sessions-section-heading">
                <span className={`ui-pill ${searchState.mode === "simulation" ? "ui-pill--live" : "ui-pill--focus"}`}>
                  {searchState.mode === "simulation" ? "Simulation" : "Lookback"}
                </span>
                <h1>{formatEventSessionLabel(sessionQuery.data.event_name, sessionQuery.data.session_name)}</h1>
                <p>
                  Imported {formatDateTime(sessionQuery.data.imported_at)}. Layouts stay separate from widgets: you choose a layout here, then the renderer mounts the widgets that layout references.
                </p>
              </div>

              <div className="sessions-workspace__aside">
                <div className="sessions-summary-card">
                  <div>
                    <span className="sessions-summary-card__label">State</span>
                    <strong>{sessionQuery.data.state}</strong>
                  </div>
                  <div>
                    <span className="sessions-summary-card__label">Entries</span>
                    <strong>{sessionQuery.data.entry_count}</strong>
                  </div>
                  <div>
                    <span className="sessions-summary-card__label">Ticks</span>
                    <strong>{sessionQuery.data.tick_count}</strong>
                  </div>
                </div>

                <div className="sessions-actions">
                  <Link to="/sessions?view=explorer" className="button-secondary">
                    Browse another session
                  </Link>
                </div>
              </div>
            </header>

            <div className="sessions-workspace__body">
              <aside className="sessions-workspace__rail">
                <div className="sessions-mode-grid sessions-mode-grid--workspace">
                  <button
                    type="button"
                    className={`sessions-mode-card${searchState.mode === "lookback" ? " is-active" : ""}`}
                    onClick={() =>
                      updateSearchState(searchState, setSearchParams, {
                        mode: "lookback",
                        layoutId: selectedLayout?.audience === "session-lookback" ? selectedLayout.id : null,
                      })
                    }
                  >
                    <span className="ui-pill ui-pill--focus">Lookback</span>
                    <h3>Session lookback</h3>
                    <p>Driver and lap controls stay active for full-session or lap-specific widgets.</p>
                  </button>

                  <button
                    type="button"
                    className={`sessions-mode-card${searchState.mode === "simulation" ? " is-active" : ""}`}
                    onClick={() =>
                      updateSearchState(searchState, setSearchParams, {
                        mode: "simulation",
                        layoutId: selectedLayout?.audience === "live-race" ? selectedLayout.id : null,
                        lap: "all",
                      })
                    }
                  >
                    <span className="ui-pill ui-pill--live">Simulation</span>
                    <h3>Replay command</h3>
                    <p>Replay mode stays on live-race layouts only.</p>
                  </button>
                </div>

                {searchState.mode === "simulation" ? (
                  <SimulationReplayBar />
                ) : (
                  <LookbackControls
                    entries={entries}
                    selectedDriverIds={validDriverIds}
                    lapOptions={lapOptions}
                    currentLap={searchState.lap}
                    onToggleDriver={(driverId) => {
                      const next = validDriverIds.includes(driverId)
                        ? validDriverIds.filter((item) => item !== driverId)
                        : [...validDriverIds, driverId];

                      updateSearchState(searchState, setSearchParams, { driverIds: next });
                    }}
                    onLapChange={(lap) => updateSearchState(searchState, setSearchParams, { lap })}
                  />
                )}

                <section className="sessions-layout-gallery sessions-layout-gallery--rail">
                  <div className="sessions-subheading">
                    <h2>Layouts</h2>
                    <p>Pick a layout to give telemetry the full stage.</p>
                  </div>

                  <div className="sessions-layout-grid">
                    {resolvedLayouts.map((layout) => (
                      <button
                        key={layout.id}
                        type="button"
                        className={`sessions-layout-card${searchState.layoutId === layout.id ? " is-active" : ""}${layout.isValid ? "" : " is-disabled"}`}
                        onClick={() => layout.isValid && updateSearchState(searchState, setSearchParams, { layoutId: layout.id })}
                        disabled={!layout.isValid}
                      >
                        <div className="sessions-layout-card__header">
                          <span className={`ui-pill ${layout.source === "builtin" ? "ui-pill--ready" : "ui-pill--focus"}`}>
                            {layout.source === "builtin" ? "Built-in" : "Your layout"}
                          </span>
                          <small>{layout.config.sections.length} sections</small>
                        </div>
                        <h3>{layout.name}</h3>
                        <p>{layout.description ?? "Custom layout without a description."}</p>
                        <footer>
                          <span>Updated {formatDateTime(layout.updatedAt)}</span>
                          {!layout.isValid ? <span>{layout.invalidReason}</span> : null}
                        </footer>
                      </button>
                    ))}
                  </div>
                </section>
              </aside>

              <section className="sessions-workspace__stage">
                <div className="sessions-workspace__stage-header">
                  <div className="sessions-subheading">
                    <h2>{selectedLayout?.name ?? "Telemetry stage"}</h2>
                    <p>
                      {selectedLayout
                        ? selectedLayout.description ?? "The selected layout mounts its widget set here."
                        : "Choose a layout from the left rail to mount its widgets and start telemetry queries."}
                    </p>
                  </div>

                  {selectedLayout ? (
                    <span className={`ui-pill ${selectedLayout.source === "builtin" ? "ui-pill--ready" : "ui-pill--focus"}`}>
                      {selectedLayout.source === "builtin" ? "Built-in layout" : "Saved layout"}
                    </span>
                  ) : null}
                </div>

                <div className="sessions-workspace__stage-body">
                  {!selectedLayout ? (
                    <div className="sessions-empty-state">Choose a layout to mount its widgets and start telemetry queries.</div>
                  ) : !selectedLayout.isValid ? (
                    <div className="sessions-empty-state sessions-empty-state--error">
                      This saved layout is not usable in the current build. Pick another layout to continue.
                    </div>
                  ) : searchState.mode === "lookback" && validDriverIds.length === 0 ? (
                    <div className="sessions-empty-state">Choose at least one driver to populate the lookback workspace.</div>
                  ) : (
                    <DashboardRenderer config={selectedLayout.config} />
                  )}
                </div>
              </section>
            </div>
          </section>
        </div>
      </SessionWorkspaceProvider>
    </PageContainer>
  );
}

function LookbackControls({
  entries,
  selectedDriverIds,
  lapOptions,
  currentLap,
  onToggleDriver,
  onLapChange,
}: {
  entries: SessionEntryDto[];
  selectedDriverIds: string[];
  lapOptions: number[];
  currentLap: SessionWorkspaceSearchState["lap"];
  onToggleDriver: (driverId: string) => void;
  onLapChange: (lap: SessionWorkspaceSearchState["lap"]) => void;
}) {
  return (
    <section className="sessions-controls">
      <div className="sessions-subheading">
        <h2>Lookback controls</h2>
        <p>Unlimited driver selection is allowed. Widgets decide whether they use all laps or require one lap.</p>
      </div>

      <div className="sessions-driver-grid">
        {entries.map((entry) => (
          <button
            key={entry.id}
            type="button"
            className={`sessions-driver-chip${selectedDriverIds.includes(entry.id) ? " is-active" : ""}`}
            onClick={() => onToggleDriver(entry.id)}
          >
            <span>{getEntryDisplayName(entry)}</span>
            <small>{entry.team_name ?? `#${entry.car_number}`}</small>
          </button>
        ))}
      </div>

      <label className="sessions-select-field">
        <span>Lap</span>
        <select
          value={currentLap === "all" ? "all" : String(currentLap)}
          onChange={(event) => onLapChange(event.target.value === "all" ? "all" : Number(event.target.value))}
        >
          <option value="all">All laps</option>
          {lapOptions.map((lap) => (
            <option key={lap} value={lap}>
              Lap {lap}
            </option>
          ))}
        </select>
      </label>

      {selectedDriverIds.length > 4 ? (
        <div className="sessions-empty-state">
          Large comparisons are allowed, but some widgets will feel heavier once you move beyond four drivers.
        </div>
      ) : null}
    </section>
  );
}

function SimulationReplayBar() {
  const workspace = useSessionWorkspace();
  const replay = workspace.replay;
  const currentLap =
    replay.leaderLaps.find((lap) => {
      const start = lap.lap_start_time_ms ?? 0;
      const end = lap.lap_end_time_ms ?? Number.MAX_SAFE_INTEGER;
      return replay.currentTimeMs >= start && replay.currentTimeMs <= end;
    }) ?? null;

  return (
    <section className="sessions-controls sessions-controls--simulation">
      <div className="sessions-subheading">
        <h2>Replay controls</h2>
        <p>Simulation mode stays on live-race layouts only and advances against imported session ticks.</p>
      </div>

      <div className="sessions-replay-summary">
        <span className="ui-pill ui-pill--live">{currentLap ? `Lap ${currentLap.lap_number}` : "Lap timeline"}</span>
        <strong>{formatSessionClock(replay.currentTimeMs)}</strong>
      </div>

      <div className="sessions-replay-timeline">
        <div className="sessions-replay-timeline__laps">
          {replay.leaderLaps.slice(0, 20).map((lap) => (
            <span
              key={lap.id}
              className={`sessions-replay-lap${currentLap?.id === lap.id ? " is-active" : ""}`}
              title={formatLapTime(lap.lap_time_ms)}
            >
              L{lap.lap_number}
            </span>
          ))}
        </div>

        <input
          type="range"
          min={replay.minTimeMs}
          max={replay.maxTimeMs || replay.minTimeMs + 1}
          value={replay.currentTimeMs}
          onChange={(event) => replay.setCurrentTimeMs(Number(event.target.value))}
        />
      </div>

      <div className="sessions-replay-actions">
        <button type="button" className="button-primary" onClick={replay.togglePlayback}>
          {replay.isPlaying ? "Pause" : "Start"}
        </button>
        <button type="button" className="button-secondary" onClick={replay.resetPlayback}>
          Reset
        </button>

        <div className="sessions-speed-list">
          {REPLAY_SPEEDS.map((speed) => (
            <button
              key={speed}
              type="button"
              className={`sessions-speed-chip${replay.speedMultiplier === speed ? " is-active" : ""}`}
              onClick={() => replay.setSpeedMultiplier(speed)}
            >
              {speed}x
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function updateSearchState(
  currentState: SessionWorkspaceSearchState,
  setSearchParams: ReturnType<typeof useSearchParams>[1],
  patch: Partial<SessionWorkspaceSearchState>,
) {
  setSearchParams(
    buildSessionWorkspaceSearchParams({
      ...currentState,
      ...patch,
    }),
    { replace: true },
  );
}
