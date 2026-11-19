import { useMemo, useState } from "react";
import { useSessionTrackStatusEventsQuery } from "../../../data/queries/sessions.queries";
import { useWorkspaceEntryLapsResource } from "../../../features/sessions/session-data.hooks";
import {
  useReplayTime,
  useSessionWorkspace,
} from "../../../features/sessions/SessionWorkspaceContext";
import {
  formatLapTime,
  getEntryDisplayName,
} from "../../../features/sessions/session-utils";
import { WidgetCard } from "../../shared/WidgetCard";
import {
  WidgetEmpty,
  WidgetError,
  WidgetLoading,
} from "../../shared/WidgetState";
import { StintAnalysisChart } from "../components/StintAnalysisChart";
import { ChartDriverPicker } from "../components/ChartDriverPicker";
import type {
  StintFilterState,
  StintSeries,
  TelemetryWidgetOptions,
} from "../models";
import {
  buildStintAnalysis,
  formatDegradation,
  getCompoundColor,
  getCompoundLabel,
  summarizeStints,
} from "../utils/stint-analysis";

export function StintAnalysisWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as TelemetryWidgetOptions;
  const workspace = useSessionWorkspace();
  const replayTimeMs = useReplayTime("review");
  const [driverFocus, setDriverFocus] = useState("");
  const [trendPreference, setTrendPreference] = useState<boolean>();
  const [filters, setFilters] = useState<StintFilterState>({
    cleanOnly: true,
    hidePitLaps: true,
    hideNeutralizedLaps: true,
    hideOutliers: true,
    showTrackStatus: true,
  });
  const [hiddenStintKeys, setHiddenStintKeys] = useState<Set<string>>(
    () => new Set(),
  );
  const laps = useWorkspaceEntryLapsResource({
    entryMode: "selected",
    enabled: workspace.selectedEntries.length > 0,
  });
  const trackStatusEvents = useSessionTrackStatusEventsQuery(
    workspace.sessionId,
    { limit: 2000 },
    (workspace.session.track_status_event_count ?? 0) > 0,
  );
  const currentTimeLimitMs =
    workspace.mode === "simulation" ? replayTimeMs : undefined;
  const analysis = useMemo(
    () =>
      buildStintAnalysis(
        workspace.selectedEntries,
        laps.dataByEntryId,
        filters,
        currentTimeLimitMs,
        trackStatusEvents.data ?? [],
      ),
    [
      currentTimeLimitMs,
      filters,
      laps.dataByEntryId,
      trackStatusEvents.data,
      workspace.selectedEntries,
    ],
  );
  const focusedId = workspace.selectedEntries.some(
    (entry) => entry.id === driverFocus,
  )
    ? driverFocus
    : "";
  const chartSeries = focusedId
    ? analysis.series.filter((stint) => stint.entryId === focusedId)
    : analysis.series;
  const showTrend =
    trendPreference ??
    (Boolean(focusedId) || workspace.selectedEntries.length <= 6);
  const visibleSeries = chartSeries.filter(
    (stint) => !hiddenStintKeys.has(stint.key),
  );
  const summary = summarizeStints(visibleSeries);

  if (workspace.selectedEntries.length === 0) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Stint Analysis"}>
        <WidgetEmpty message="Choose drivers to compare stint pace and tyre behavior." />
      </WidgetCard>
    );
  }

  if (laps.isLoading) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Stint Analysis"}>
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (laps.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Stint Analysis"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  return (
    <WidgetCard
      title={widgetOptions.title ?? "Stint Analysis"}
      description={
        workspace.mode === "simulation"
          ? "Completed stint laps up to the replay clock, plotted on absolute session lap numbers."
          : "Stint pace and degradation by absolute session lap number."
      }
      actions={
        <div className="stint-toolbar">
          <ChartDriverPicker
            drivers={workspace.selectedEntries.map((entry) => ({
              entry,
              id: entry.id,
              label: getEntryDisplayName(entry),
            }))}
            value={focusedId}
            onChange={setDriverFocus}
          />
          <StintFilterButton
            active={filters.cleanOnly}
            label="Clean"
            onClick={() =>
              setFilters((current) => ({
                ...current,
                cleanOnly: !current.cleanOnly,
              }))
            }
          />
          <StintFilterButton
            active={filters.hidePitLaps}
            label="Pit"
            onClick={() =>
              setFilters((current) => ({
                ...current,
                hidePitLaps: !current.hidePitLaps,
              }))
            }
          />
          <StintFilterButton
            active={filters.hideNeutralizedLaps}
            label="SC/VSC"
            onClick={() =>
              setFilters((current) => ({
                ...current,
                hideNeutralizedLaps: !current.hideNeutralizedLaps,
              }))
            }
          />
          <StintFilterButton
            active={filters.hideOutliers}
            label="Outliers"
            onClick={() =>
              setFilters((current) => ({
                ...current,
                hideOutliers: !current.hideOutliers,
              }))
            }
          />
          <StintFilterButton
            active={showTrend}
            label="Trend"
            onClick={() => setTrendPreference(!showTrend)}
          />
          <StintFilterButton
            active={filters.showTrackStatus}
            label="Status"
            onClick={() =>
              setFilters((current) => ({
                ...current,
                showTrackStatus: !current.showTrackStatus,
              }))
            }
          />
        </div>
      }
    >
      <StintAnalysisChart
        series={visibleSeries}
        statusBands={filters.showTrackStatus ? analysis.statusBands : []}
        showTrend={showTrend}
        emptyMessage={
          chartSeries.length && !visibleSeries.length
            ? "All stints are hidden. Turn on a stint below to see its laps."
            : "No completed stint laps matched the displayed drivers and filters."
        }
      />

      <div className="stint-dashboard">
        <div className="stint-summary" aria-label="Stint analysis summary">
          <StintSummaryItem
            label="Best Median"
            value={
              summary.bestMedian
                ? formatLapTime(summary.bestMedian.medianLapMs)
                : "--:--.---"
            }
            detail={
              summary.bestMedian
                ? formatStintName(summary.bestMedian)
                : "No visible stint"
            }
          />
          <StintSummaryItem
            label="Longest"
            value={
              summary.longestStint
                ? `${summary.longestStint.lapFrom}-${summary.longestStint.lapTo}`
                : "N/A"
            }
            detail={
              summary.longestStint
                ? formatStintName(summary.longestStint)
                : "No visible stint"
            }
          />
          <StintSummaryItem
            label="Degradation"
            value={
              summary.highestDegradation
                ? formatDegradation(
                    summary.highestDegradation.degradationMsPerLap,
                  )
                : "N/A"
            }
            detail={
              summary.highestDegradation
                ? formatStintName(summary.highestDegradation)
                : "No positive slope"
            }
          />
          <StintSummaryItem
            label="Visible Laps"
            value={summary.visibleLapCount}
            detail={`${summary.hiddenLapCount} excluded by lap filters`}
          />
        </div>

        {chartSeries.length ? (
          <details className="stint-details">
            <summary>Driver and stint visibility</summary>
            <div
              className="stint-control-grid"
              aria-label="Stint visibility controls"
            >
              {groupSeriesByEntry(chartSeries).map(([entryId, stints]) => (
                <div key={entryId} className="stint-driver-panel">
                  <div className="stint-driver-panel__header">
                    <span>
                      <i style={{ backgroundColor: stints[0]?.driverColor }} />
                      {stints[0]?.driverLabel ?? "Driver"}
                    </span>
                    <small>
                      {
                        stints.filter(
                          (stint) => !hiddenStintKeys.has(stint.key),
                        ).length
                      }
                      /{stints.length} on
                    </small>
                  </div>
                  <div className="stint-driver-panel__rows">
                    {stints.map((stint) => {
                      const active = !hiddenStintKeys.has(stint.key);
                      return (
                        <button
                          key={stint.key}
                          type="button"
                          aria-pressed={active}
                          className={`stint-toggle-row${active ? " is-active" : ""}`}
                          onClick={() =>
                            toggleStint(
                              hiddenStintKeys,
                              setHiddenStintKeys,
                              stint.key,
                            )
                          }
                        >
                          <span className="stint-toggle-row__compound">
                            <i
                              style={{
                                backgroundColor: getCompoundColor(
                                  stint.compound,
                                ),
                              }}
                            />
                            {`S${stint.stintNumber} · ${getCompoundLabel(stint.compound)}`}
                          </span>
                          <span className="stint-toggle-row__meta">
                            {`L${stint.lapFrom}-${stint.lapTo}`}
                          </span>
                          <span className="stint-toggle-row__switch">
                            {active ? "ON" : "OFF"}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </details>
        ) : null}
      </div>
    </WidgetCard>
  );
}

function StintFilterButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`stint-filter-button${active ? " is-active" : ""}`}
      aria-pressed={active}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

function StintSummaryItem({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <div className="stint-summary__item">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function groupSeriesByEntry(series: StintSeries[]) {
  const grouped = new Map<string, StintSeries[]>();
  for (const stint of series) {
    grouped.set(stint.entryId, [...(grouped.get(stint.entryId) ?? []), stint]);
  }

  return Array.from(grouped.entries()).map(
    ([entryId, stints]) =>
      [
        entryId,
        stints.sort((left, right) => left.stintNumber - right.stintNumber),
      ] as const,
  );
}

function toggleStint(
  hiddenStintKeys: Set<string>,
  setHiddenStintKeys: (value: Set<string>) => void,
  stintKey: string,
) {
  const next = new Set(hiddenStintKeys);
  if (next.has(stintKey)) {
    next.delete(stintKey);
  } else {
    next.add(stintKey);
  }
  setHiddenStintKeys(next);
}

function formatStintName(stint: StintSeries) {
  return `${stint.driverLabel} S${stint.stintNumber}`;
}
