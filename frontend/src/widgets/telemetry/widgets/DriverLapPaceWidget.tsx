import { DriverSelect } from "../../../components/DriverSelect";
import { driverOption } from "../../../components/driver-select-options";
import { useMemo, useState } from "react";
import { useSessionTrackStatusEventsQuery } from "../../../data/queries/sessions.queries";
import { useWorkspaceEntryLapsResource } from "../../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import {
  formatLapTime,
  getEntryDisplayName,
} from "../../../features/sessions/session-utils";
import { WidgetCard } from "../../shared/WidgetCard";
import { useWidgetSize } from "../../shared/widget-size";
import {
  WidgetEmpty,
  WidgetError,
  WidgetLoading,
} from "../../shared/WidgetState";
import { LapTimeComparisonChart } from "../components/LapTimeComparisonChart";
import { ChartDriverPicker } from "../components/ChartDriverPicker";
import type {
  LapFilterState,
  LapReferenceMode,
  TelemetryWidgetOptions,
} from "../models";
import {
  buildLapReferenceSeries,
  buildLapTimeAnalysis,
  summarizeLapPace,
} from "../utils/lap-pace";

export function LapTimeTrendWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as TelemetryWidgetOptions;
  const workspace = useSessionWorkspace();
  const { compact } = useWidgetSize();
  const [driverFocus, setDriverFocus] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<LapFilterState>({
    cleanOnly: true,
    hidePitLaps: true,
    hideNeutralizedLaps: true,
    hideOutliers: true,
    smooth: false,
    showTrackStatus: true,
  });
  const [referenceMode, setReferenceMode] =
    useState<LapReferenceMode>("average");
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
    () =>
      buildLapTimeAnalysis(
        workspace.selectedEntries,
        laps.dataByEntryId,
        filters,
        trackStatusEvents.data ?? [],
      ),
    [
      filters,
      laps.dataByEntryId,
      trackStatusEvents.data,
      workspace.selectedEntries,
    ],
  );
  const referenceSeries = useMemo(
    () => buildLapReferenceSeries(referenceMode, analysis.series),
    [analysis.series, referenceMode],
  );
  const focusedId = workspace.selectedEntries.some(
    (entry) => entry.id === driverFocus,
  )
    ? driverFocus
    : "";
  const series = focusedId
    ? analysis.series.filter((item) => item.entryId === focusedId)
    : analysis.series;
  const summary = summarizeLapPace(series);
  const fastest = summary.fastestPoint;
  const strongestMedian = summary.bestMedian;
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
          <ChartDriverPicker
            drivers={workspace.selectedEntries.map((entry) => ({
              entry,
              id: entry.id,
              label: getEntryDisplayName(entry),
            }))}
            value={focusedId}
            onChange={setDriverFocus}
          />
          {compact ? (
            <button
              type="button"
              className="lap-pace-toggle"
              aria-expanded={filtersOpen}
              onClick={() => setFiltersOpen(!filtersOpen)}
            >
              Filters &amp; reference
            </button>
          ) : null}
          {!compact || filtersOpen ? (
            <>
              <label className="lap-pace-reference">
                <span>Reference</span>
                <DriverSelect
                  aria-label="Reference"
                  value={referenceMode}
                  onChange={(value) =>
                    setReferenceMode(
                      value as LapReferenceMode,
                    )
                  }
                  options={[
                    { value: "average", label: "Field average" },
                    { value: "best", label: "Field best" },
                    { value: "none", label: "None" },
                    ...workspace.selectedEntries.map((entry) => driverOption(entry, `entry:${entry.id}`)),
                  ]}
                />
              </label>
              <div
                className="lap-pace-toggle-group"
                aria-label="Lap chart filters"
              >
                <LapFilterButton
                  active={filters.cleanOnly}
                  label="Clean"
                  onClick={() =>
                    setFilters((current) => ({
                      ...current,
                      cleanOnly: !current.cleanOnly,
                    }))
                  }
                />
                <LapFilterButton
                  active={filters.hidePitLaps}
                  label="Pit"
                  onClick={() =>
                    setFilters((current) => ({
                      ...current,
                      hidePitLaps: !current.hidePitLaps,
                    }))
                  }
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
                  onClick={() =>
                    setFilters((current) => ({
                      ...current,
                      hideOutliers: !current.hideOutliers,
                    }))
                  }
                />
                <LapFilterButton
                  active={filters.smooth}
                  label="Smooth"
                  onClick={() =>
                    setFilters((current) => ({
                      ...current,
                      smooth: !current.smooth,
                    }))
                  }
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
            </>
          ) : null}
        </div>
      }
    >
      <LapTimeComparisonChart
        series={series}
        referenceSeries={referenceSeries}
        statusBands={filters.showTrackStatus ? analysis.statusBands : []}
        emptyMessage="Lap-time data was not available for the selected drivers."
      />

      <div className="lap-pace-summary" aria-label="Lap pace summary">
        <div className="lap-pace-summary__item">
          <span>Fastest</span>
          <strong>
            {fastest ? formatLapTime(fastest.lapTimeMs) : "--:--.---"}
          </strong>
          <small>
            {fastest
              ? `${fastest.label} L${fastest.lapNumber}`
              : "No clean laps"}
          </small>
        </div>
        <div className="lap-pace-summary__item">
          <span>Best Median</span>
          <strong>
            {strongestMedian
              ? formatLapTime(strongestMedian.medianMs)
              : "--:--.---"}
          </strong>
          <small>{strongestMedian?.label ?? "No median"}</small>
        </div>
        <div className="lap-pace-summary__item">
          <span>Laps Shown</span>
          <strong>{summary.visibleLapCount}</strong>
          <small>{summary.hiddenLapCount} excluded by lap filters</small>
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
