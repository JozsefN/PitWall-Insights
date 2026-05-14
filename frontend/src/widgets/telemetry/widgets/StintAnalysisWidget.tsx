import { useMemo, useState } from "react";
import { useSessionTrackStatusEventsQuery } from "../../../data/queries/sessions.queries";
import { useWorkspaceEntryLapsResource } from "../../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import { formatLapTime } from "../../../features/sessions/session-utils";
import { WidgetCard } from "../../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../../shared/WidgetState";
import { StintAnalysisChart } from "../components/StintAnalysisChart";
import type { StintFilterState, StintSeries, TelemetryWidgetOptions } from "../models";
import {
  buildStintAnalysis,
  formatDegradation,
  getCompoundColor,
  getCompoundLabel,
  getCompoundShortLabel,
} from "../utils/stint-analysis";

export function StintAnalysisWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as TelemetryWidgetOptions;
  const workspace = useSessionWorkspace();
  const [filters, setFilters] = useState<StintFilterState>({
    cleanOnly: true,
    hidePitLaps: true,
    hideNeutralizedLaps: true,
    hideOutliers: true,
    showTrend: true,
    showTrackStatus: true,
  });
  const [hiddenStintKeys, setHiddenStintKeys] = useState<Set<string>>(() => new Set());
  const laps = useWorkspaceEntryLapsResource({
    entryMode: "selected",
    enabled: workspace.selectedEntries.length > 0,
  });
  const trackStatusEvents = useSessionTrackStatusEventsQuery(
    workspace.sessionId,
    { limit: 2000 },
    (workspace.session.track_status_event_count ?? 0) > 0,
  );
  const currentTimeLimitMs = workspace.mode === "simulation" ? workspace.replay.currentTimeMs : undefined;
  const analysis = useMemo(
    () =>
      buildStintAnalysis(
        workspace.selectedEntries,
        laps.dataByEntryId,
        filters,
        currentTimeLimitMs,
        trackStatusEvents.data ?? [],
      ),
    [currentTimeLimitMs, filters, laps.dataByEntryId, trackStatusEvents.data, workspace.selectedEntries],
  );
  const visibleSeries = analysis.series.filter((stint) => !hiddenStintKeys.has(stint.key));

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
          <StintFilterButton
            active={filters.cleanOnly}
            label="Clean"
            onClick={() => setFilters((current) => ({ ...current, cleanOnly: !current.cleanOnly }))}
          />
          <StintFilterButton
            active={filters.hidePitLaps}
            label="Pit"
            onClick={() => setFilters((current) => ({ ...current, hidePitLaps: !current.hidePitLaps }))}
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
            onClick={() => setFilters((current) => ({ ...current, hideOutliers: !current.hideOutliers }))}
          />
          <StintFilterButton
            active={filters.showTrend}
            label="Trend"
            onClick={() => setFilters((current) => ({ ...current, showTrend: !current.showTrend }))}
          />
          <StintFilterButton
            active={filters.showTrackStatus}
            label="Status"
            onClick={() => setFilters((current) => ({ ...current, showTrackStatus: !current.showTrackStatus }))}
          />
        </div>
      }
    >
      <StintAnalysisChart
        series={analysis.series}
        statusBands={filters.showTrackStatus ? analysis.statusBands : []}
        hiddenStintKeys={hiddenStintKeys}
        showTrend={filters.showTrend}
        emptyMessage="No stint laps matched the current drivers and filters."
      />

      <div className="stint-dashboard">
        <div className="stint-summary" aria-label="Stint analysis summary">
          <StintSummaryItem
            label="Best Median"
            value={analysis.bestMedian ? formatLapTime(analysis.bestMedian.medianLapMs) : "--:--.---"}
            detail={analysis.bestMedian ? formatStintName(analysis.bestMedian) : "No visible stint"}
          />
          <StintSummaryItem
            label="Longest"
            value={analysis.longestStint ? `${analysis.longestStint.lapFrom}-${analysis.longestStint.lapTo}` : "N/A"}
            detail={analysis.longestStint ? formatStintName(analysis.longestStint) : "No visible stint"}
          />
          <StintSummaryItem
            label="Degradation"
            value={analysis.highestDegradation ? formatDegradation(analysis.highestDegradation.degradationMsPerLap) : "N/A"}
            detail={analysis.highestDegradation ? formatStintName(analysis.highestDegradation) : "No positive slope"}
          />
          <StintSummaryItem
            label="Visible Laps"
            value={analysis.visibleLapCount}
            detail={`${analysis.hiddenLapCount} hidden by filters`}
          />
        </div>

        <div className="stint-control-grid" aria-label="Stint visibility controls">
          {groupSeriesByEntry(analysis.series).map(([entryId, stints]) => (
            <div key={entryId} className="stint-driver-panel">
              <div className="stint-driver-panel__header">
                <span>
                  <i style={{ backgroundColor: stints[0]?.driverColor }} />
                  {stints[0]?.driverLabel ?? "Driver"}
                </span>
                <small>{stints.filter((stint) => !hiddenStintKeys.has(stint.key)).length}/{stints.length} on</small>
              </div>
              <div className="stint-driver-panel__rows">
                {stints.map((stint) => {
                  const active = !hiddenStintKeys.has(stint.key);
                  return (
                    <button
                      key={stint.key}
                      type="button"
                      className={`stint-toggle-row${active ? " is-active" : ""}`}
                      onClick={() => toggleStint(hiddenStintKeys, setHiddenStintKeys, stint.key)}
                    >
                      <span className="stint-toggle-row__compound">
                        <i style={{ backgroundColor: getCompoundColor(stint.compound) }} />
                        {`S${stint.stintNumber} - ${getCompoundLabel(stint.compound)} (${getCompoundShortLabel(stint.compound)})`}
                      </span>
                      <span className="stint-toggle-row__meta">
                        {`L${stint.lapFrom}-${stint.lapTo}`}
                      </span>
                      <span className="stint-toggle-row__switch">{active ? "ON" : "OFF"}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {visibleSeries.length === 0 ? (
          <p className="stint-empty-note">All stints are hidden. Turn at least one stint back on to see the chart.</p>
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

  return Array.from(grouped.entries()).map(([entryId, stints]) => [
    entryId,
    stints.sort((left, right) => left.stintNumber - right.stintNumber),
  ] as const);
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
