import { useMemo, useState } from "react";
import { useSessionTrackStatusEventsQuery } from "../../../data/queries/sessions.queries";
import { useWorkspaceEntryLapsResource } from "../../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import { formatLapTime, getEntryDisplayName } from "../../../features/sessions/session-utils";
import { WidgetCard } from "../../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../../shared/WidgetState";
import { LapTimeComparisonChart } from "../components/LapTimeComparisonChart";
import type { LapFilterState, LapReferenceMode, TelemetryWidgetOptions } from "../models";
import {
  buildLapReferenceSeries,
  buildLapTimeAnalysis,
} from "../utils/lap-pace";

export function LapTimeTrendWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as TelemetryWidgetOptions;
  const workspace = useSessionWorkspace();
  const [filters, setFilters] = useState<LapFilterState>({
    cleanOnly: true,
    hidePitLaps: true,
    hideNeutralizedLaps: true,
    hideOutliers: true,
    smooth: false,
    showTrackStatus: true,
  });
  const [referenceMode, setReferenceMode] = useState<LapReferenceMode>("average");
  const laps = useWorkspaceEntryLapsResource({
    entryMode: "selected",
    enabled: workspace.selectedEntries.length > 0,
  });
  const trackStatusEvents = useSessionTrackStatusEventsQuery(
    workspace.sessionId,
    { limit: 2000 },
    (workspace.session.track_status_event_count ?? 0) > 0,
  );
  const analysis = useMemo(
    () => buildLapTimeAnalysis(workspace.selectedEntries, laps.dataByEntryId, filters, trackStatusEvents.data ?? []),
    [filters, laps.dataByEntryId, trackStatusEvents.data, workspace.selectedEntries],
  );
  const referenceSeries = useMemo(
    () => buildLapReferenceSeries(referenceMode, analysis.series),
    [analysis.series, referenceMode],
  );
  const fastest = analysis.fastestPoint;
  const strongestMedian = analysis.bestMedian;
  const referenceLabel = referenceSeries?.label ?? "None";

  if (workspace.selectedEntries.length === 0) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Time Trend"}>
        <WidgetEmpty message="Choose drivers to compare lap-time evolution." />
      </WidgetCard>
    );
  }

  if (laps.isLoading) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Time Trend"}>
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (laps.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Time Trend"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  return (
    <WidgetCard
      title={widgetOptions.title ?? "Driver Lap Pace"}
      description="Lap time evolution with clean-lap filters, reference comparison, and hover values."
      actions={
        <div className="lap-pace-toolbar">
          <label className="lap-pace-reference">
            <span>Reference</span>
            <select
              value={referenceMode}
              onChange={(event) => setReferenceMode(event.currentTarget.value as LapReferenceMode)}
            >
              <option value="average">Avg</option>
              <option value="best">Best</option>
              <option value="none">None</option>
              {workspace.selectedEntries.map((entry) => (
                <option key={entry.id} value={`entry:${entry.id}`}>
                  {getEntryDisplayName(entry)}
                </option>
              ))}
            </select>
          </label>
          <div className="lap-pace-toggle-group" aria-label="Lap chart filters">
            <LapFilterButton
              active={filters.cleanOnly}
              label="Clean"
              onClick={() => setFilters((current) => ({ ...current, cleanOnly: !current.cleanOnly }))}
            />
            <LapFilterButton
              active={filters.hidePitLaps}
              label="Pit"
              onClick={() => setFilters((current) => ({ ...current, hidePitLaps: !current.hidePitLaps }))}
            />
            <LapFilterButton
              active={filters.hideNeutralizedLaps}
              label="SC/VSC"
              onClick={() =>
                setFilters((current) => ({
                  ...current,
                  hideNeutralizedLaps: !current.hideNeutralizedLaps,
                }))
              }
            />
            <LapFilterButton
              active={filters.hideOutliers}
              label="Outliers"
              onClick={() => setFilters((current) => ({ ...current, hideOutliers: !current.hideOutliers }))}
            />
            <LapFilterButton
              active={filters.smooth}
              label="Smooth"
              onClick={() => setFilters((current) => ({ ...current, smooth: !current.smooth }))}
            />
            <LapFilterButton
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
        </div>
      }
    >
      <LapTimeComparisonChart
        series={analysis.series}
        referenceSeries={referenceSeries}
        statusBands={filters.showTrackStatus ? analysis.statusBands : []}
        emptyMessage="Lap-time data was not available for the selected drivers."
      />

      <div className="lap-pace-summary" aria-label="Lap pace summary">
        <div className="lap-pace-summary__item">
          <span>Fastest</span>
          <strong>{fastest ? formatLapTime(fastest.lapTimeMs) : "--:--.---"}</strong>
          <small>{fastest ? `${fastest.label} L${fastest.lapNumber}` : "No clean laps"}</small>
        </div>
        <div className="lap-pace-summary__item">
          <span>Best Median</span>
          <strong>{strongestMedian ? formatLapTime(strongestMedian.medianMs) : "--:--.---"}</strong>
          <small>{strongestMedian?.label ?? "No median"}</small>
        </div>
        <div className="lap-pace-summary__item">
          <span>Laps Shown</span>
          <strong>{analysis.visibleLapCount}</strong>
          <small>{analysis.hiddenLapCount} hidden by filters</small>
        </div>
        <div className="lap-pace-summary__item">
          <span>Reference</span>
          <strong>{referenceLabel}</strong>
          <small>{filters.smooth ? "Smoothed trace" : "Raw trace"}</small>
        </div>
      </div>
    </WidgetCard>
  );
}

function LapFilterButton({
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
      className={`lap-pace-toggle${active ? " is-active" : ""}`}
      aria-pressed={active}
      onClick={onClick}
    >
      {label}
    </button>
  );
}
