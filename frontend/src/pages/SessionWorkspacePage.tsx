import { useQueries, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { PageContainer } from "../app/layout/PageContanier";
import { listEntryLaps } from "../data/api/sessions.api";
import { FavoriteButton } from "../features/dashboards/FavoriteButton";
import { useLayoutFavoritesQuery, useSetLayoutFavoriteMutation, useLayoutsQuery } from "../data/queries/layouts.queries";
import { useImportJobQuery } from "../data/queries/session-import.queries";
import { useSessionEntriesQuery, useSessionQuery, useSessionReplayTimelineQuery } from "../data/queries/sessions.queries";
import { useTelemetryMaterializationJobsQuery } from "../data/queries/telemetry-materialization.queries";
import { useAuthSession } from "../features/auth/useAuthSession";
import { clearTelemetryWarmupJobId } from "../features/sessions/session-import-warmup";
import { writeStoredSessionWorkspace } from "../features/sessions/session-resume";
import { sessionHostFlag } from "../features/circuits/circuit-catalog";
import { SessionWorkspaceProvider } from "../features/sessions/SessionWorkspaceContext";
import { WorkspaceDashboardDataProvider } from "../features/sessions/WorkspaceDashboardDataProvider";
import { SessionModeToggle } from "../features/sessions/SessionModeToggle";
import { SessionTimingTower } from "../features/sessions/SessionTimingTower";
import { getLayoutGuide, recommendedLayoutId } from "../features/dashboards/layout-guides";
import { sortLayoutsForSession } from "../features/dashboards/layout-catalog";
import { getAudienceForMode, getResolvedLayoutById, resolveAllLayouts, checkLayoutInSession } from "../features/sessions/session-layouts";
import {
  buildSessionWorkspaceSearchParams,
  parseSessionWorkspaceSearchParams,
  type SessionWorkspaceSearchState,
} from "../features/sessions/session-workspace.search";
import { starterDrivers } from "../features/sessions/session-utils";
import { LookbackControls, SimulationReplayBar } from "../features/sessions/SessionWorkspaceControls";
import { useTelemetryWarmupJobId } from "../features/sessions/use-telemetry-warmup-job-id";
import {
  TelemetryWarmupBanner, WorkspaceStatusStrip, type WorkspaceStatusItem,
} from "../features/sessions/WorkspaceTelemetryStatus";
import {
  getTelemetryStatusLabel, getTelemetryWarmupTitle, formatTelemetryJobSummary,
  compareTelemetryJobsByActivity, isActiveTelemetryJob,
} from "../features/sessions/telemetry-status";
import { LayoutPreview } from "../features/dashboards/LayoutPreview";
import { Availability } from "../features/dashboards/Availability";
import { classifySession, layoutModes, modeLabel, sessionKindLabel, supportedSessionKinds, widgetIds } from "../features/dashboards/compatibility";
import { DashboardRenderer } from "../widgets/shared/DashboardRenderer";
import "./sessions-page.css";

export function SessionWorkspacePage() {
  const { sessionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const telemetryWarmupJobId = useTelemetryWarmupJobId(sessionId);

  const telemetryWarmupQuery = useImportJobQuery(telemetryWarmupJobId ?? undefined, Boolean(telemetryWarmupJobId));
  const telemetryWarmupActive =
    telemetryWarmupQuery.data?.status === "queued" || telemetryWarmupQuery.data?.status === "running";
  const sessionQuery = useSessionQuery(sessionId, true, telemetryWarmupActive ? 3000 : false);
  const entriesQuery = useSessionEntriesQuery(sessionId);
  const authSession = useAuthSession();
  const searchState = parseSessionWorkspaceSearchParams(searchParams);
  const audience = getAudienceForMode(searchState.mode);
  const layoutsQuery = useLayoutsQuery(authSession.data?.authenticated === true);
  const favoritesQuery = useLayoutFavoritesQuery();
  const favoriteMutation = useSetLayoutFavoriteMutation();
  const kind = sessionQuery.data && classifySession(sessionQuery.data);
  const allLayouts = resolveAllLayouts(layoutsQuery.data, favoritesQuery.data);
  const evaluatedLayouts = allLayouts.map(layout => checkLayoutInSession(layout, audience, kind));
  const resolvedLayouts = evaluatedLayouts.filter(layout => layout.isValid).sort(sortLayoutsForSession(audience, kind, favoritesQuery.data));
  const unavailableLayouts = evaluatedLayouts.filter(layout => !layout.isValid && (layout.source === "user" || layout.id === searchState.layoutId));
  const selectedLayout = getResolvedLayoutById(searchState.layoutId, evaluatedLayouts);
  const alternativeAudience = audience === "live-race" ? "session-lookback" : "live-race";
  const originalSelection = getResolvedLayoutById(searchState.layoutId, allLayouts);
  const alternateLayout = originalSelection && checkLayoutInSession(originalSelection, alternativeAudience, kind);
  const ticksQuery = useSessionReplayTimelineQuery(sessionId, searchState.mode === "simulation");
  const telemetryJobsQuery = useTelemetryMaterializationJobsQuery(50, { refetchActive: Boolean(sessionId) });

  const entries = entriesQuery.data ?? [];
  const sessionTelemetryJobs = (telemetryJobsQuery.data?.jobs ?? [])
    .filter((job) => job.session_id === sessionId)
    .sort(compareTelemetryJobsByActivity);
  const activeTelemetryJobs = sessionTelemetryJobs.filter(isActiveTelemetryJob);
  const recentTelemetryJobs = sessionTelemetryJobs.slice(0, 4);
  const validDriverIds = searchState.driverIds.filter((driverId) =>
    entries.some((entry) => entry.id === driverId),
  );
  const validDriverIdsKey = validDriverIds.join(",");

  const lapQueries = useQueries({
    queries: validDriverIds.map((entryId) => ({
      queryKey: ["sessions", sessionId, "entries", entryId, "laps"],
      queryFn: () => listEntryLaps(sessionId as string, entryId),
      enabled: searchState.mode === "lookback" && validDriverIds.length > 0,
    })),
  });

  const lapOptions = Array.from(
    new Set(lapQueries.flatMap((query) => (query.data ?? []).map((lap) => lap.lap_number))),
  ).sort((left, right) => left - right);
  const lapControlsLoading = lapQueries.some((query) => query.isLoading);
  const lapOptionsKnown = entriesQuery.isSuccess && lapQueries.every((query) => query.isSuccess);
  const layoutsLoading = layoutsQuery.isLoading;
  const replayTicksLoading = searchState.mode === "simulation" && ticksQuery.isPending;

  useEffect(() => {
    if (!sessionId || telemetryWarmupQuery.data?.status !== "completed") {
      return;
    }

    clearTelemetryWarmupJobId(sessionId);
    void queryClient.invalidateQueries({ queryKey: ["sessions", sessionId] });
  }, [queryClient, sessionId, telemetryWarmupQuery.data?.status]);

  useEffect(() => {
    if (!entriesQuery.isSuccess) return;
    if (validDriverIds.length === searchState.driverIds.length) {
      return;
    }

    updateSearchState(searchState, setSearchParams, { driverIds: validDriverIds });
  }, [entriesQuery.isSuccess, searchState, setSearchParams, validDriverIds]);

  useEffect(() => {
    if (!lapOptionsKnown || searchState.mode !== "lookback" || searchState.lap === "all" || lapOptions.includes(searchState.lap)) {
      return;
    }

    updateSearchState(searchState, setSearchParams, { lap: "all" });
  }, [lapOptions, lapOptionsKnown, searchState, setSearchParams]);

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

  if (!sessionQuery.data || !entriesQuery.data) {
    return (
      <PageContainer>
        <div className="sessions-empty-state sessions-empty-state--error">The session workspace could not be loaded.</div>
      </PageContainer>
    );
  }

  const handleSetDriverIds = (driverIds: string[]) => {
    updateSearchState(searchState, setSearchParams, { driverIds });
  };
  const handleToggleDriver = (driverId: string) => {
    const next = validDriverIds.includes(driverId)
      ? validDriverIds.filter((item) => item !== driverId)
      : [...validDriverIds, driverId];

    handleSetDriverIds(next);
  };

  const workspaceStatusItems: WorkspaceStatusItem[] = [
    {
      label: "Session",
      value: sessionQuery.isRefetchError ? "Refresh failed" : sessionQuery.data.state,
      detail: `${sessionQuery.data.entry_count} entries`,
      tone: sessionQuery.isRefetchError ? "warning" : "ready",
    },
    {
      label: "Entries",
      value: entriesQuery.isRefetchError ? "Refresh failed" : `${entries.length} loaded`,
      detail: "Driver roster",
      tone: entriesQuery.isRefetchError ? "warning" : "ready",
    },
    {
      label: searchState.mode === "simulation" ? "Replay" : "Laps",
      value:
        searchState.mode === "simulation"
          ? replayTicksLoading
            ? "Loading timeline"
            : ticksQuery.isError ? "Unavailable" : "Ready"
          : validDriverIds.length === 0
            ? "Pick drivers"
            : lapControlsLoading
              ? "Loading laps"
              : `${lapOptions.length} laps`,
      detail: searchState.mode === "simulation" ? `${validDriverIds.length} selected drivers` : "Lap selector",
      tone:
        searchState.mode === "simulation"
          ? replayTicksLoading
            ? "loading"
            : ticksQuery.isError ? "warning" : "ready"
          : validDriverIds.length === 0
            ? "idle"
            : lapControlsLoading
              ? "loading"
              : "ready",
    },
    {
      label: "Layouts",
      value: layoutsLoading ? "Loading" : `${resolvedLayouts.length} available`,
      detail: selectedLayout?.name ?? "No layout selected",
      tone: layoutsLoading ? "loading" : selectedLayout ? "ready" : "idle",
    },
    {
      label: "Telemetry",
      value: activeTelemetryJobs.length > 0
        ? `${activeTelemetryJobs.length} preparing`
        : telemetryWarmupActive
          ? getTelemetryWarmupTitle(sessionQuery.data.telemetry_status, telemetryWarmupQuery.data?.status, telemetryWarmupQuery.data?.progress_stage)
          : recentTelemetryJobs.some((job) => job.status === "completed")
            ? "Cache ready"
            : getTelemetryStatusLabel(sessionQuery.data.telemetry_status),
      detail: activeTelemetryJobs[0]
        ? formatTelemetryJobSummary(activeTelemetryJobs[0])
        : telemetryWarmupActive
          ? "Background import"
          : recentTelemetryJobs[0]
            ? formatTelemetryJobSummary(recentTelemetryJobs[0])
            : "On-demand cache",
      tone:
        activeTelemetryJobs.length > 0
          ? "loading"
          : telemetryWarmupQuery.data?.status === "failed" || sessionQuery.data.telemetry_status === "unavailable"
          ? "warning"
          : telemetryWarmupActive
            ? "loading"
            : sessionQuery.data.telemetry_status === "loaded" || recentTelemetryJobs.some((job) => job.status === "completed")
              ? "ready"
              : "idle",
    },
  ];

  const hostFlag = sessionHostFlag(sessionQuery.data);

  return (
    <PageContainer size="wide">
      <SessionWorkspaceProvider
        key={sessionId}
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
        <WorkspaceDashboardDataProvider>
        <div className="sessions-shell">
          <section className="sessions-workspace">
            <header className="feature-banner sessions-workspace__hero" data-host-flag={hostFlag}>
              {hostFlag ? (
                <img
                  className="sessions-workspace__flag"
                  src={`${import.meta.env.BASE_URL}host-flags/${hostFlag}.webp`}
                  alt=""
                  aria-hidden="true"
                />
              ) : null}
              {sessionQuery.data.round_number ? (
                <span className="sessions-workspace__round" aria-hidden="true">
                  {String(sessionQuery.data.round_number).padStart(2, "0")}
                </span>
              ) : null}
              <div className="sessions-section-heading">
                <p className="feature-banner__detail">
                  {sessionQuery.data.season_year}
                  {sessionQuery.data.round_number ? ` · Round ${sessionQuery.data.round_number}` : ""}
                  {` · ${sessionQuery.data.session_name}`}
                </p>
                <h1 className="feature-banner__title">{sessionQuery.data.event_name}</h1>
              </div>

              <div className="sessions-workspace__aside">
                <div className="sessions-actions">
                  <Link to="/sessions?view=explorer" className="button-secondary">
                    Change session
                  </Link>
                  {selectedLayout?.isValid ? <a href="#session-dashboard" className="button-primary">Jump to dashboard ↓</a> : null}
                </div>
              </div>
            </header>

            <details className="sessions-data-status">
              <summary>Data status{activeTelemetryJobs.length || telemetryWarmupActive ? " · Preparing telemetry" : ""}</summary>
              <TelemetryWarmupBanner
              telemetryStatus={sessionQuery.data.telemetry_status}
              jobStatus={telemetryWarmupQuery.data?.status}
              jobStage={telemetryWarmupQuery.data?.progress_stage}
              errorMessage={telemetryWarmupQuery.data?.error_message}
              materializationJobs={recentTelemetryJobs}
              materializationLoading={telemetryJobsQuery.isLoading}
              />

              <WorkspaceStatusStrip items={workspaceStatusItems} />
            </details>

            <div className="sessions-workspace__control-deck">
              <section className="sessions-control-panel sessions-control-panel--mode">
                <SessionModeToggle value={searchState.mode} onChange={(mode) =>
                  updateSearchState(searchState, setSearchParams, { mode, lap: mode === "simulation" ? "all" : searchState.lap })
                } />
              </section>

              <section className="sessions-control-panel sessions-control-panel--layouts">
                <div className="sessions-subheading">
                  <div className="sessions-layout-heading">
                    <h2>Choose a layout</h2>
                    <Link to={`/dashboard-builder?audience=${audience}${kind ? `&sessionKind=${kind}` : ""}`} className="sessions-builder-link">Dashboard Builder <span aria-hidden="true">↗</span></Link>
                  </div>
                  <p>{kind ? sessionKindLabel[kind] : "This session"} · {modeLabel[audience]}</p>
                </div>

                {favoriteMutation.isError ? <p role="alert">Could not update favorites. Please try again.</p> : null}
                {layoutsLoading ? (
                  <div className="sessions-empty-state">Loading layouts...</div>
                ) : resolvedLayouts.length === 0 ? (
                  <div className="sessions-empty-state">No layouts fit this session and mode. Check restrictions below or create a compatible layout.</div>
                ) : (
                  <div className="sessions-layout-strip" aria-label="Compatible layouts">
                    {resolvedLayouts.map((layout) => {
                      const guide = getLayoutGuide(layout.id);
                      const recommended = layout.id === recommendedLayoutId(audience, kind);
                      return (
                      <div className="sessions-layout-item" key={layout.id}>
                      <button
                        type="button"
                        className={`sessions-layout-card${searchState.layoutId === layout.id ? " is-active" : ""}${recommended ? " is-recommended" : ""}`}
                        aria-label={layout.name}
                        aria-pressed={searchState.layoutId === layout.id}
                        onClick={() => updateSearchState(searchState, setSearchParams, {
                          layoutId: layout.id,
                          driverIds: recommended && validDriverIds.length === 0 ? starterDrivers(entries) : validDriverIds,
                        })}
                      >
                        <div className="sessions-layout-card__header">
                          <span className="layout-guide-label" data-recommended={recommended}>{guide?.label ?? "Your layout"}</span>
                        </div>
                        <h3>{layout.name}</h3>
                        <p>{guide?.summary ?? layout.description ?? "Saved dashboard"}</p>
                        <LayoutPreview config={layout.config} compact />
                      </button>
                      <FavoriteButton name={layout.name} favorite={favoritesQuery.data?.includes(layout.id) ?? false}
                        disabled={favoriteMutation.isPending || favoritesQuery.isPending || favoritesQuery.isError}
                        onToggle={() => favoriteMutation.mutate({ layoutId: layout.id, favorite: !favoritesQuery.data?.includes(layout.id) })} />
                      </div>
                    );})}
                  </div>
                )}
                {unavailableLayouts.length > 0 ? (
                  <details className="layout-unavailable-list">
                    <summary>Unavailable layouts ({unavailableLayouts.length})</summary>
                    <ul>
                      {unavailableLayouts.map((layout) => (
                        <li key={layout.id}>
                          <strong>{layout.name}</strong>
                          <p>{layout.invalidReason}</p>
                          {layout.source === "user" ? (
                            <Link to={`/dashboard-builder?${new URLSearchParams({ audience: layout.audience, layout: layout.id })}`}>
                              View in Dashboard Builder
                            </Link>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : null}
              </section>

              <section className="sessions-control-panel sessions-control-panel--runtime">
                {searchState.mode === "simulation" ? (
                  <SimulationReplayBar
                    entries={entries}
                    selectedDriverIds={validDriverIds}
                    timelineLoading={replayTicksLoading}
                    timelineError={ticksQuery.isError}
                    onToggleDriver={handleToggleDriver}
                    onSelectAllDrivers={() => handleSetDriverIds(entries.map((entry) => entry.id))}
                    onClearDrivers={() => handleSetDriverIds([])}
                  />
                ) : (
                  <LookbackControls
                    entries={entries}
                    selectedDriverIds={validDriverIds}
                    lapOptions={lapOptions}
                    isLapLoading={lapControlsLoading}
                    currentLap={searchState.lap}
                    onToggleDriver={handleToggleDriver}
                    onSelectAllDrivers={() => handleSetDriverIds(entries.map((entry) => entry.id))}
                    onClearDrivers={() => handleSetDriverIds([])}
                    onLapChange={(lap) => updateSearchState(searchState, setSearchParams, { lap })}
                  />
                )}
              </section>
            </div>

            <div className="sessions-workspace__body" id="session-dashboard" tabIndex={-1}>
              <section className="sessions-workspace__stage">
                {!selectedLayout?.isValid ? <div className="sessions-workspace__stage-header">
                  <div className="sessions-subheading">
                    <h2>{selectedLayout?.name ?? "Session dashboard"}</h2>
                    <p>
                      {selectedLayout
                        ? selectedLayout.description ?? "Your selected session view."
                        : "Choose a layout above to start exploring telemetry."}
                    </p>
                  </div>

                  {selectedLayout ? (
                    <span className={`ui-pill ${selectedLayout.source === "builtin" ? "ui-pill--ready" : "ui-pill--focus"}`}>
                      {selectedLayout.source === "builtin" ? "Built-in layout" : "Saved layout"}
                    </span>
                  ) : null}
                </div> : null}

                <div className="sessions-workspace__stage-body">
                  {!selectedLayout ? (
                    <div className="sessions-empty-state">{searchState.layoutId && !layoutsLoading ? "The linked layout is unavailable. Choose a compatible layout above." : "Choose a compatible layout above to start exploring telemetry."}</div>
                  ) : !selectedLayout.isValid ? (
                    <div className="layout-availability-message" role="status">
                      <strong>{selectedLayout.name} cannot open here.</strong> {selectedLayout.invalidReason}
                      <Availability
                        modes={layoutModes(selectedLayout)}
                        kinds={supportedSessionKinds(widgetIds(selectedLayout.config), selectedLayout.config.sessionKind)}
                      />
                      <div className="layout-availability-actions">
                        {alternateLayout?.isValid ? <button className="button-secondary" type="button" onClick={() => updateSearchState(searchState, setSearchParams, {mode: alternativeAudience === "live-race" ? "simulation" : "lookback", lap: "all"})}>Open in {modeLabel[alternativeAudience]}</button> : null}
                        {selectedLayout.source === "user" ? <Link className="button-secondary" to={`/dashboard-builder?${new URLSearchParams({audience: selectedLayout.audience, layout: selectedLayout.id})}`}>Review saved layout</Link> : null}
                      </div>
                    </div>
                  ) : (
                    <DashboardRenderer config={{ ...selectedLayout.config, subtitle: selectedLayout.config.subtitle || selectedLayout.description || undefined }} />
                  )}
                </div>
              </section>
              <SessionTimingTower />
            </div>
          </section>
        </div>
        </WorkspaceDashboardDataProvider>
      </SessionWorkspaceProvider>
    </PageContainer>
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
