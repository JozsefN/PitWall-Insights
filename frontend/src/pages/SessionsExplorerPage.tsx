import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { getImportFeedback } from "../features/sessions/import-feedback";
import { PageContainer } from "../app/layout/PageContanier";
import type { SessionCatalogItemDto, SessionImportRequestDto } from "../data/contracts/sessions.contracts";
import {
  useImportSessionMutation,
  useSessionCatalogQuery,
  useSessionQuery,
} from "../data/queries/sessions.queries";
import {
  buildStoredSessionWorkspaceHref,
  readStoredSessionWorkspace,
  writeStoredSessionWorkspace,
} from "../features/sessions/session-resume";
import { buildSessionWorkspaceHref } from "../features/sessions/session-workspace.search";
import { formatDateTime } from "../features/sessions/session-utils";
import type { SessionWorkspaceMode } from "../widgets/registry/widget.types";
import { SessionModeToggle } from "../features/sessions/SessionModeToggle";
import "./sessions-page.css";

type CatalogGroup = {
  key: string;
  roundLabel: string;
  title: string;
  subtitle: string;
  sessions: SessionCatalogItemDto[];
};

const CURRENT_YEAR = new Date().getFullYear();
const SEASONS = Array.from({ length: CURRENT_YEAR - 2022 }, (_, index) => CURRENT_YEAR - index);

export function SessionsExplorerPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [season, setSeason] = useState(() => SEASONS.includes(Number(searchParams.get("season"))) ? Number(searchParams.get("season")) : CURRENT_YEAR);
  const [mode, setMode] = useState<SessionWorkspaceMode>(() => searchParams.get("mode") === "simulation" ? "simulation" : "lookback");
  const [selectedWeekendKey, setSelectedWeekendKey] = useState<string | null>(() => searchParams.get("weekend"));
  const [selectedSessionKey, setSelectedSessionKey] = useState<string | null>(() => searchParams.get("session"));

  const catalogQuery = useSessionCatalogQuery(season);
  const coreImportMutation = useImportSessionMutation();
  const storedWorkspace = readStoredSessionWorkspace();
  const resumeHref = buildStoredSessionWorkspaceHref(storedWorkspace);
  const resumeSessionQuery = useSessionQuery(
    storedWorkspace?.sessionId,
    Boolean(storedWorkspace),
  );
  const catalogItems = catalogQuery.data ?? [];
  const groupedCatalog = groupCatalog(catalogItems);
  const activeWeekendKey =
    selectedWeekendKey && groupedCatalog.some((group) => group.key === selectedWeekendKey)
      ? selectedWeekendKey
      : groupedCatalog[0]?.key ?? null;
  const selectedGroup =
    groupedCatalog.find((group) => group.key === activeWeekendKey) ?? null;
  const activeSessionKey =
    selectedSessionKey &&
    selectedGroup?.sessions.some((item) => item.source_session_key === selectedSessionKey)
      ? selectedSessionKey
      : selectedGroup?.sessions[0]?.source_session_key ?? null;
  const selectedSession =
    selectedGroup?.sessions.find((item) => item.source_session_key === activeSessionKey) ?? null;
  const showExplorer = searchParams.get("view") === "explorer";
  const importProgress = getCoreImportProgress();
  const isImportActive = coreImportMutation.isPending;
  const importFeedback = getImportFeedback(coreImportMutation.error);

  useEffect(() => {
    if (!resumeHref || showExplorer || !resumeSessionQuery.data) {
      return;
    }

    navigate(resumeHref, { replace: true });
  }, [navigate, resumeHref, resumeSessionQuery.data, showExplorer]);

  function handlePrepare() {
    if (!selectedSession || selectedSession.available_for_import === false) {
      return;
    }

    const request: SessionImportRequestDto = {
      season_year: selectedSession.season_year,
      round_number: selectedSession.round_number ?? 0,
      session_name: selectedSession.session_name,
      source_session_key: selectedSession.source_session_key,
      import_profile: "core",
      data_provider: "openf1",
    };
    const nextMode = mode;

    coreImportMutation.mutate(
      request,
      {
        onSuccess: (data) => {
          const nextState = {
            mode: nextMode,
            layoutId: null,
            driverIds: [],
            lap: "all" as const,
          };
          const nextHref = buildSessionWorkspaceHref(data.id, nextState);

          writeStoredSessionWorkspace({
            sessionId: data.id,
            state: nextState,
            updatedAt: new Date().toISOString(),
          });

          void queryClient.invalidateQueries({ queryKey: ["sessions"] });
          navigate(nextHref, { replace: true });
        },
      },
    );
  }

  if (!showExplorer && storedWorkspace && (resumeSessionQuery.isLoading || resumeSessionQuery.data)) {
    return (
      <PageContainer>
        <div className="sessions-empty-state">
          {resumeSessionQuery.isLoading
            ? "Opening the active session workspace..."
            : "Resuming the active session workspace..."}
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <div className="sessions-shell">
        <header className="feature-banner sessions-section-heading">
          <h1 className="feature-banner__title">Session Explorer</h1>
          <p className="feature-banner__detail">Pick a session and open it in Lookback or Replay.</p>
        </header>
        <section className="surface-card sessions-explorer">
          <div className="sessions-explorer__left">
            <div className="sessions-explorer__filters">
              <label className="sessions-select-field">
                <span>Season</span>
                <select
                  aria-label="Season"
                  value={season}
                  onChange={(event) => {
                    setSeason(Number(event.target.value));
                    setSelectedWeekendKey(null);
                    setSelectedSessionKey(null);
                  }}
                >
                  {SEASONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>

              <label className="sessions-select-field">
                <span>Race weekend</span>
                <select
                  aria-label="Race weekend"
                  value={activeWeekendKey ?? ""}
                  onChange={(event) => {
                    setSelectedWeekendKey(event.target.value || null);
                    setSelectedSessionKey(null);
                  }}
                  disabled={catalogQuery.isLoading || groupedCatalog.length === 0}
                >
                  {groupedCatalog.length === 0 ? (
                    <option value="">No weekend available</option>
                  ) : (
                    groupedCatalog.map((group) => (
                      <option key={group.key} value={group.key}>
                        {group.roundLabel} - {group.title}
                      </option>
                    ))
                  )}
                </select>
              </label>
            </div>

            <p className="sessions-source-note">OpenF1 historical data · 2023 onwards · No external account needed</p>

            <div className="sessions-catalog">
              {catalogQuery.isLoading ? (
                <div className="sessions-empty-state">Loading session catalog...</div>
              ) : catalogQuery.isError ? (
                <div className="sessions-empty-state sessions-empty-state--error">
                  The OpenF1 session catalog could not be loaded.
                </div>
              ) : !selectedGroup ? (
                <div className="sessions-empty-state">No sessions were returned for this season.</div>
              ) : (
                <article className="sessions-event-group">
                  <header className="sessions-event-group__header">
                    <div>
                      <span className="sessions-round-pill">{selectedGroup.roundLabel}</span>
                      <h2>{selectedGroup.title}</h2>
                      <p>{selectedGroup.subtitle}</p>
                    </div>
                    <small className="sessions-event-group__count">
                      {selectedGroup.sessions.length} {selectedGroup.sessions.length === 1 ? "session" : "sessions"}
                    </small>
                  </header>

                  <div className="sessions-event-group__list">
                    {selectedGroup.sessions.map((item) => {
                      const isSelected = item.source_session_key === selectedSession?.source_session_key;

                      return (
                        <button
                          key={item.source_session_key}
                          type="button"
                          className={`sessions-session-button${isSelected ? " is-selected" : ""}`}
                          aria-pressed={isSelected}
                          onClick={() => {
                            setSelectedSessionKey(item.source_session_key);
                          }}
                        >
                          <strong>{item.session_name}</strong>
                          <span>{formatDateTime(item.scheduled_start_utc)}</span>
                        </button>
                      );
                    })}
                  </div>
                </article>
              )}
            </div>
          </div>

          <aside className="sessions-explorer__right">
            <div className="sessions-section-heading">
              <h2>{selectedSession?.session_name ?? "Pick a session"}</h2>
              <p>
                {selectedSession
                  ? `${selectedSession.event_name} · ${formatDateTime(selectedSession.scheduled_start_utc)}`
                  : "Choose a session to continue."}
              </p>
            </div>

            {resumeHref && resumeSessionQuery.data ? (
              <div className="sessions-prepared-card">
                <div className="sessions-subheading">
                  <h3>Current workspace</h3>
                  <p>
                    Resume the Lookback or Replay workspace you last opened.
                  </p>
                </div>

                <div className="sessions-summary-card">
                  <div>
                    <span className="sessions-summary-card__label">Event</span>
                    <strong>{resumeSessionQuery.data.event_name}</strong>
                  </div>
                  <div>
                    <span className="sessions-summary-card__label">Session</span>
                    <strong>{resumeSessionQuery.data.session_name}</strong>
                  </div>
                  <div>
                    <span className="sessions-summary-card__label">Imported</span>
                    <strong>{formatDateTime(resumeSessionQuery.data.imported_at)}</strong>
                  </div>
                </div>

                <div className="sessions-actions">
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={() => navigate(resumeHref)}
                  >
                    Resume workspace
                  </button>
                </div>
              </div>
            ) : null}

            {selectedSession ? (
              <>
                <SessionModeToggle value={mode} onChange={setMode} />

                <div className="sessions-actions">
                  {selectedSession.available_for_import === false && <p role="status" className="sessions-source-note">{selectedSession.unavailable_reason ?? "This session is not available as history yet."}</p>}
                  <button
                    type="button"
                    className="button-primary"
                    onClick={handlePrepare}
                    disabled={isImportActive || selectedSession.available_for_import === false}
                  >
                    {isImportActive ? importProgress.buttonLabel : "Load session"}
                  </button>
                </div>

                {isImportActive ? (
                  <div className="sessions-import-status">
                    <div className="sessions-import-status__header">
                      <span>{importProgress.label}</span>
                      <strong>{importProgress.percent}%</strong>
                    </div>
                    <div className="sessions-import-progress" aria-hidden="true">
                      <span style={{ width: `${importProgress.percent}%` }} />
                    </div>
                    <p>{importProgress.detail}</p>
                  </div>
                ) : null}

                {coreImportMutation.isError ? (
                  <div className="sessions-empty-state sessions-empty-state--error" role="alert">
                    <p>{importFeedback.message}</p>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="sessions-empty-state">
                Choose a session from the left to prepare the workspace.
              </div>
            )}
          </aside>
        </section>
      </div>
    </PageContainer>
  );
}

function groupCatalog(items: SessionCatalogItemDto[]): CatalogGroup[] {
  const groups = new Map<string, CatalogGroup>();

  for (const item of items) {
    const existing = groups.get(item.source_event_key);

    if (existing) {
      existing.sessions.push(item);
      continue;
    }

    groups.set(item.source_event_key, {
      key: item.source_event_key,
      roundLabel: item.round_number != null ? `R${String(item.round_number).padStart(2, "0")}` : item.is_testing ? "Test" : "Event",
      title: item.event_name,
      subtitle: item.location ?? item.country ?? item.official_event_name ?? "Weekend",
      sessions: [item],
    });
  }

  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      sessions: [...group.sessions].sort(compareCatalogSessions),
    }))
    .sort((left, right) => {
      const leftRound = left.sessions[0]?.round_number ?? 0;
      const rightRound = right.sessions[0]?.round_number ?? 0;

      if (leftRound !== rightRound) {
        return leftRound - rightRound;
      }

      return compareCatalogSessions(left.sessions[0], right.sessions[0]);
    });
}

function compareCatalogSessions(
  left?: SessionCatalogItemDto,
  right?: SessionCatalogItemDto,
) {
  if (!left && !right) {
    return 0;
  }

  if (!left) {
    return 1;
  }

  if (!right) {
    return -1;
  }

  const leftTime = left.scheduled_start_utc ? new Date(left.scheduled_start_utc).getTime() : Number.MAX_SAFE_INTEGER;
  const rightTime = right.scheduled_start_utc ? new Date(right.scheduled_start_utc).getTime() : Number.MAX_SAFE_INTEGER;

  if (leftTime !== rightTime) {
    return leftTime - rightTime;
  }

  return left.session_name.localeCompare(right.session_name);
}

function getCoreImportProgress() {
  return {
    percent: 55,
    label: "Opening core session",
    buttonLabel: "Opening core session...",
    detail: "Loading the lightweight profile now. Telemetry slices will be cached when widgets request them.",
  };
}

