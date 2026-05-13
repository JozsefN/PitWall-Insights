import { useQueries, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { PageContainer } from "../app/layout/PageContanier";
import { listEntryLaps } from "../data/api/sessions.api";
import type { SessionEntryDto, SessionTelemetryStatus } from "../data/contracts/sessions.contracts";
import type { ImportJobStage, ImportJobStatus } from "../data/contracts/session-import.contracts";
import type { TelemetryMaterializationJobDto } from "../data/contracts/telemetry-materialization.contracts";
import { useLayoutsQuery } from "../data/queries/layouts.queries";
import { useImportJobQuery } from "../data/queries/session-import.queries";
import { useSessionEntriesQuery, useSessionQuery, useSessionTicksQuery } from "../data/queries/sessions.queries";
import { useTelemetryMaterializationJobsQuery } from "../data/queries/telemetry-materialization.queries";
import { useAuthSession } from "../features/auth/useAuthSession";
import {
  clearTelemetryWarmupJobId,
  readTelemetryWarmupJobId,
  TELEMETRY_WARMUP_JOB_EVENT,
  type TelemetryWarmupJobEventDetail,
} from "../features/sessions/session-import-warmup";
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

type WorkspaceStatusItem = {
  label: string;
  value: string;
  detail: string;
  tone: "ready" | "loading" | "warning" | "idle";
};

export function SessionWorkspacePage() {
  const { sessionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [telemetryWarmupJobId, setTelemetryWarmupJobId] = useState<string | null>(() =>
    sessionId ? readTelemetryWarmupJobId(sessionId) : null,
  );

  const telemetryWarmupQuery = useImportJobQuery(telemetryWarmupJobId ?? undefined, Boolean(telemetryWarmupJobId));
  const telemetryWarmupActive =
    telemetryWarmupQuery.data?.status === "queued" || telemetryWarmupQuery.data?.status === "running";
  const sessionQuery = useSessionQuery(sessionId, true, telemetryWarmupActive ? 3000 : false);
  const entriesQuery = useSessionEntriesQuery(sessionId);
  const authSession = useAuthSession();
  const searchState = parseSessionWorkspaceSearchParams(searchParams);
  const audience = getAudienceForMode(searchState.mode);
  const layoutsQuery = useLayoutsQuery(authSession.data?.authenticated === true);
  const resolvedLayouts = resolveWorkspaceLayouts(layoutsQuery.data, audience);
  const selectedLayout = getResolvedLayoutById(searchState.layoutId, resolvedLayouts);
  const ticksQuery = useSessionTicksQuery(sessionId, { limit: 50000 }, searchState.mode === "simulation");
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
      queryKey: ["sessions", sessionId, "entries", entryId, "laps", "controls"],
      queryFn: () => listEntryLaps(sessionId as string, entryId),
      enabled: searchState.mode === "lookback" && validDriverIds.length > 0,
    })),
  });

  const lapOptions = Array.from(
    new Set(lapQueries.flatMap((query) => (query.data ?? []).map((lap) => lap.lap_number))),
  ).sort((left, right) => left - right);
  const lapControlsLoading = lapQueries.some((query) => query.isLoading || query.isFetching);
  const layoutsLoading = layoutsQuery.isLoading || layoutsQuery.isFetching;
  const replayTicksLoading = searchState.mode === "simulation" && (ticksQuery.isLoading || ticksQuery.isFetching);

  useEffect(() => {
    setTelemetryWarmupJobId(sessionId ? readTelemetryWarmupJobId(sessionId) : null);
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    function handleTelemetryWarmupJob(event: Event) {
      const detail = (event as CustomEvent<TelemetryWarmupJobEventDetail>).detail;

      if (detail?.sessionId === sessionId) {
        setTelemetryWarmupJobId(detail.jobId);
      }
    }

    window.addEventListener(TELEMETRY_WARMUP_JOB_EVENT, handleTelemetryWarmupJob);

    return () => {
      window.removeEventListener(TELEMETRY_WARMUP_JOB_EVENT, handleTelemetryWarmupJob);
    };
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || telemetryWarmupQuery.data?.status !== "completed") {
      return;
    }

    clearTelemetryWarmupJobId(sessionId);
    setTelemetryWarmupJobId(null);
    void queryClient.invalidateQueries({ queryKey: ["sessions", sessionId] });
  }, [queryClient, sessionId, telemetryWarmupQuery.data?.status]);

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
      value: sessionQuery.isFetching ? "Refreshing" : sessionQuery.data.state,
      detail: `${sessionQuery.data.entry_count} entries`,
      tone: sessionQuery.isFetching ? "loading" : "ready",
    },
    {
      label: "Entries",
      value: entriesQuery.isFetching ? "Refreshing" : `${entries.length} loaded`,
      detail: "Driver roster",
      tone: entriesQuery.isFetching ? "loading" : "ready",
    },
    {
      label: searchState.mode === "simulation" ? "Replay" : "Laps",
      value:
        searchState.mode === "simulation"
          ? replayTicksLoading
            ? "Loading ticks"
            : `${ticksQuery.data?.length ?? 0} ticks`
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
            : "ready"
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

            <TelemetryWarmupBanner
              telemetryStatus={sessionQuery.data.telemetry_status}
              jobStatus={telemetryWarmupQuery.data?.status}
              jobStage={telemetryWarmupQuery.data?.progress_stage}
              errorMessage={telemetryWarmupQuery.data?.error_message}
              materializationJobs={recentTelemetryJobs}
              materializationLoading={telemetryJobsQuery.isFetching}
            />

            <WorkspaceStatusStrip items={workspaceStatusItems} />

            <div className="sessions-workspace__control-deck">
              <section className="sessions-control-panel sessions-control-panel--mode">
                <div className="sessions-subheading">
                  <h2>Mode</h2>
                  <p>Switching mode changes the controls and layout audience, but keeps the same imported session.</p>
                </div>

                <div className="sessions-mode-grid sessions-mode-grid--workspace">
                  <button
                    type="button"
                    className={`sessions-mode-card${searchState.mode === "lookback" ? " is-active" : ""}`}
                    aria-pressed={searchState.mode === "lookback"}
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
                    aria-pressed={searchState.mode === "simulation"}
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
              </section>

              <section className="sessions-control-panel sessions-control-panel--runtime">
                {searchState.mode === "simulation" ? (
                  <SimulationReplayBar
                    entries={entries}
                    selectedDriverIds={validDriverIds}
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

              <section className="sessions-control-panel sessions-control-panel--layouts">
                <div className="sessions-subheading">
                  <h2>Layouts</h2>
                  <p>Pick a layout here. The full stage below is reserved for the selected dashboard.</p>
                </div>

                {layoutsLoading ? (
                  <div className="sessions-empty-state">Loading layouts...</div>
                ) : resolvedLayouts.length === 0 ? (
                  <div className="sessions-empty-state">No layouts are available for this mode.</div>
                ) : (
                  <div className="sessions-layout-strip">
                    {resolvedLayouts.map((layout) => (
                      <button
                        key={layout.id}
                        type="button"
                        className={`sessions-layout-card${searchState.layoutId === layout.id ? " is-active" : ""}${layout.isValid ? "" : " is-disabled"}`}
                        aria-pressed={searchState.layoutId === layout.id}
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
                )}
              </section>
            </div>

            <div className="sessions-workspace__body">
              <section className="sessions-workspace__stage">
                <div className="sessions-workspace__stage-header">
                  <div className="sessions-subheading">
                    <h2>{selectedLayout?.name ?? "Telemetry stage"}</h2>
                    <p>
                      {selectedLayout
                        ? selectedLayout.description ?? "The selected layout mounts its widget set here."
                        : "Choose a layout from the top controls to mount its widgets and start telemetry queries."}
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

function TelemetryWarmupBanner({
  telemetryStatus,
  jobStatus,
  jobStage,
  errorMessage,
  materializationJobs,
  materializationLoading,
}: {
  telemetryStatus: SessionTelemetryStatus;
  jobStatus?: ImportJobStatus;
  jobStage?: ImportJobStage;
  errorMessage?: string | null;
  materializationJobs: TelemetryMaterializationJobDto[];
  materializationLoading: boolean;
}) {
  const activeMaterializationJobs = materializationJobs.filter(isActiveTelemetryJob);
  const latestMaterializationJob = materializationJobs[0];
  const failedMaterializationJob = materializationJobs.find((job) => job.status === "failed");

  if (telemetryStatus === "loaded" && materializationJobs.length === 0) {
    return null;
  }

  const jobActive = jobStatus === "queued" || jobStatus === "running";
  const materializationActive = activeMaterializationJobs.length > 0;
  const isError = telemetryStatus === "unavailable" || jobStatus === "failed" || Boolean(failedMaterializationJob);
  const title = materializationActive
    ? getTelemetryMaterializationTitle(activeMaterializationJobs)
    : latestMaterializationJob
      ? getTelemetryMaterializationDoneTitle(latestMaterializationJob)
      : getTelemetryWarmupTitle(telemetryStatus, jobStatus, jobStage);
  const description = materializationActive
    ? getTelemetryMaterializationDescription(activeMaterializationJobs)
    : latestMaterializationJob
      ? getTelemetryMaterializationDoneDescription(latestMaterializationJob)
      : getTelemetryWarmupDescription(telemetryStatus, jobStatus, jobStage, errorMessage);
  const jobsToShow = materializationActive
    ? activeMaterializationJobs
    : materializationJobs.filter((job) => job.status === "completed" || job.status === "failed").slice(0, 3);

  return (
    <div className={`sessions-telemetry-banner${isError ? " sessions-telemetry-banner--warning" : ""}`}>
      <div>
        <span className={`ui-pill ${jobActive || materializationActive ? "ui-pill--live" : "ui-pill--focus"}`}>
          {materializationActive ? "Telemetry cache" : jobActive ? "Warming telemetry" : "Telemetry"}
        </span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {jobsToShow.length > 0 || materializationLoading ? (
        <div className="sessions-telemetry-banner__jobs">
          {jobsToShow.map((job) => (
            <div key={job.id} className={`sessions-telemetry-job sessions-telemetry-job--${job.status}`}>
              <strong>{formatTelemetryJobSummary(job)}</strong>
              <span>{getTelemetryMaterializationStageLabel(job)}</span>
              <small>
                {job.entry_ids.length} {job.entry_ids.length === 1 ? "entry" : "entries"}
                {formatRowsWritten(job.rows_written)}
              </small>
            </div>
          ))}
          {materializationLoading ? <span className="sessions-inline-loading">Refreshing worker status...</span> : null}
        </div>
      ) : null}
      {jobActive || materializationActive ? (
        <div className="sessions-telemetry-banner__meter" aria-hidden="true">
          <span style={{ width: `${materializationActive ? getMaterializationPercent(activeMaterializationJobs[0]?.progress_stage) : getWarmupPercent(jobStage)}%` }} />
        </div>
      ) : null}
    </div>
  );
}

function getTelemetryWarmupTitle(
  telemetryStatus: SessionTelemetryStatus,
  jobStatus?: ImportJobStatus,
  jobStage?: ImportJobStage,
) {
  if (jobStatus === "failed") {
    return "Telemetry warmup failed";
  }

  if (jobStatus === "queued") {
    return "Telemetry job is queued";
  }

  if (jobStatus === "running") {
    switch (jobStage) {
      case "loading_source":
        return "Loading full telemetry";
      case "normalizing":
        return "Normalizing full telemetry";
      case "persisting":
        return "Writing telemetry cache";
      default:
        return "Preparing full telemetry";
    }
  }

  if (telemetryStatus === "partial") {
    return "Telemetry is partially available";
  }

  if (telemetryStatus === "unavailable") {
    return "Telemetry is unavailable";
  }

  return "Workspace opened on core data";
}

function getTelemetryWarmupDescription(
  telemetryStatus: SessionTelemetryStatus,
  jobStatus?: ImportJobStatus,
  jobStage?: ImportJobStage,
  errorMessage?: string | null,
) {
  if (jobStatus === "failed") {
    return errorMessage ?? "The session is still open on core data, but the background full telemetry import failed.";
  }

  if (jobStatus === "queued") {
    return "The session is usable now. Full car and position telemetry will appear after the worker claims this job.";
  }

  if (jobStatus === "running") {
    if (jobStage === "persisting") {
      return "The session stays open while the worker replaces the core cache with the full telemetry cache using the same session id.";
    }
    return "You can inspect entries, laps, events, and layouts while the worker fills the heavier telemetry cache.";
  }

  if (telemetryStatus === "partial") {
    return "FastF1 returned only part of the requested telemetry. Some widgets may have less data than expected.";
  }

  if (telemetryStatus === "unavailable") {
    return "FastF1 could not provide full telemetry for this session. Laps, entries, events, and timing context remain available.";
  }

  return "The lightweight core profile is cached. Full telemetry has not been requested or is not being tracked in this browser.";
}

function getWarmupPercent(stage?: ImportJobStage) {
  switch (stage) {
    case "queued":
      return 12;
    case "loading_source":
      return 42;
    case "normalizing":
      return 68;
    case "persisting":
      return 88;
    case "completed":
      return 100;
    default:
      return 20;
  }
}

function isActiveTelemetryJob(job: TelemetryMaterializationJobDto) {
  return job.status === "queued" || job.status === "running";
}

function compareTelemetryJobsByActivity(
  left: TelemetryMaterializationJobDto,
  right: TelemetryMaterializationJobDto,
) {
  const leftActive = isActiveTelemetryJob(left);
  const rightActive = isActiveTelemetryJob(right);

  if (leftActive !== rightActive) {
    return leftActive ? -1 : 1;
  }

  return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
}

function getTelemetryMaterializationTitle(jobs: TelemetryMaterializationJobDto[]) {
  if (jobs.length === 1) {
    return `${formatTelemetryJobSummary(jobs[0])} is being prepared`;
  }

  return `${jobs.length} telemetry cache requests are being prepared`;
}

function getTelemetryMaterializationDescription(jobs: TelemetryMaterializationJobDto[]) {
  const summaries = jobs.slice(0, 3).map((job) => `${formatTelemetryJobSummary(job)}: ${getTelemetryMaterializationStageLabel(job)}`);
  const suffix = jobs.length > summaries.length ? `, plus ${jobs.length - summaries.length} more` : "";
  return `${summaries.join("; ")}${suffix}. Widgets will read the normal telemetry API as soon as these cache segments are ready.`;
}

function getTelemetryMaterializationDoneTitle(job: TelemetryMaterializationJobDto) {
  if (job.status === "failed") {
    return `${formatTelemetryJobSummary(job)} failed`;
  }

  if (job.status === "completed") {
    return `${formatTelemetryJobSummary(job)} is cached`;
  }

  return "Telemetry cache activity";
}

function getTelemetryMaterializationDoneDescription(job: TelemetryMaterializationJobDto) {
  if (job.status === "failed") {
    return job.error_message ?? "The worker could not prepare this telemetry cache segment.";
  }

  if (job.status === "completed") {
    return `The worker completed this ${job.scope}-scope cache request. If a widget still looks empty, it is now reading sample rows rather than waiting on FastF1.`;
  }

  return "Telemetry cache status is being refreshed.";
}

function formatTelemetryJobSummary(job: TelemetryMaterializationJobDto) {
  const kindLabel = job.kinds.map((kind) => (kind === "car" ? "car" : "position")).join(" + ");
  const scopeLabel = job.scope === "lap" && job.lap_number != null ? `lap ${job.lap_number}` : "session";
  return `${capitalize(kindLabel)} telemetry, ${scopeLabel}`;
}

function getTelemetryMaterializationStageLabel(job: TelemetryMaterializationJobDto) {
  if (job.status === "queued") {
    return "Queued for worker";
  }

  if (job.status === "completed") {
    return "Completed";
  }

  if (job.status === "failed") {
    return "Failed";
  }

  switch (job.progress_stage) {
    case "loading_source":
      return "Loading FastF1 source data";
    case "normalizing":
      return "Normalizing telemetry rows";
    case "persisting":
      return "Writing cache rows";
    default:
      return "Preparing telemetry";
  }
}

function getMaterializationPercent(stage?: string) {
  switch (stage) {
    case "queued":
      return 15;
    case "loading_source":
      return 42;
    case "normalizing":
      return 68;
    case "persisting":
      return 88;
    case "completed":
      return 100;
    default:
      return 24;
  }
}

function formatRowsWritten(rowsWritten: number | null) {
  if (rowsWritten == null || rowsWritten <= 0) {
    return "";
  }

  return ` - ${rowsWritten.toLocaleString()} rows`;
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function WorkspaceStatusStrip({ items }: { items: WorkspaceStatusItem[] }) {
  return (
    <div className="sessions-status-strip" aria-label="Workspace loading status">
      {items.map((item) => (
        <div key={item.label} className={`sessions-status-item sessions-status-item--${item.tone}`}>
          <span className="sessions-status-item__dot" aria-hidden="true" />
          <div>
            <span className="sessions-status-item__label">{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.detail}</small>
          </div>
        </div>
      ))}
    </div>
  );
}

function getTelemetryStatusLabel(status: SessionTelemetryStatus) {
  switch (status) {
    case "loaded":
      return "Loaded";
    case "partial":
      return "Partial";
    case "unavailable":
      return "Unavailable";
    case "not_loaded":
    default:
      return "Lazy";
  }
}

function LookbackControls({
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
          <strong>{selectedDriverIds.length}</strong> of <strong>{entries.length}</strong> drivers selected. Widgets decide whether they use all laps or require one lap.
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
              <span className="sessions-inline-loading">Loading lap list...</span>
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
          Large comparisons are allowed, but some widgets will feel heavier once you move beyond four drivers.
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
          <button type="button" className="sessions-mini-action" onClick={onSelectAllDrivers}>
            All
          </button>
          <button type="button" className="sessions-mini-action" onClick={onClearDrivers}>
            Clear
          </button>
        </div>
      </div>

      <div className="sessions-driver-strip">
        {entries.map((entry) => {
          const isSelected = selectedDriverIds.includes(entry.id);

          return (
            <button
              key={entry.id}
              type="button"
              className={`sessions-driver-chip${isSelected ? " is-active" : ""}`}
              aria-pressed={isSelected}
              onClick={() => onToggleDriver(entry.id)}
            >
              <span>{getEntryDisplayName(entry)}</span>
              <small>{entry.team_name ?? `#${entry.car_number}`}</small>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SimulationReplayBar({
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
        <p>
          <strong>{selectedDriverIds.length}</strong> of <strong>{entries.length}</strong> drivers selected for replay widgets.
        </p>
      </div>

      <DriverSelectionControl
        entries={entries}
        selectedDriverIds={selectedDriverIds}
        onToggleDriver={onToggleDriver}
        onSelectAllDrivers={onSelectAllDrivers}
        onClearDrivers={onClearDrivers}
      />

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
