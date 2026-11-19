import { useState } from "react";
import type { EntryLapDto } from "../../../data/contracts/sessions.contracts";
import { useWorkspaceEntryLapsResource } from "../../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import {
  formatLapTime,
  getEntryAccent,
  getEntryDisplayName,
} from "../../../features/sessions/session-utils";
import { WidgetCard } from "../../shared/WidgetCard";
import {
  WidgetEmpty,
  WidgetError,
  WidgetLoading,
} from "../../shared/WidgetState";
import type { TelemetryWidgetOptions } from "../models";

const LAP_ROWS_PER_PAGE = 24;

type LapRow = { id: string; driver: string; accent: string; lap: EntryLapDto };

export function LapTableWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const widgetOptions = (options ?? {}) as TelemetryWidgetOptions;
  const workspace = useSessionWorkspace();
  const laps = useWorkspaceEntryLapsResource({
    entryMode: "selected",
    enabled: workspace.selectedEntries.length > 0,
  });

  if (workspace.selectedEntries.length === 0) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Table"}>
        <WidgetEmpty message="Choose drivers to inspect lap-by-lap data." />
      </WidgetCard>
    );
  }

  if (laps.isLoading) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Table"}>
        <WidgetLoading />
      </WidgetCard>
    );
  }

  if (laps.isError) {
    return (
      <WidgetCard title={widgetOptions.title ?? "Lap Table"}>
        <WidgetError />
      </WidgetCard>
    );
  }

  const rows = workspace.selectedEntries
    .flatMap((entry, index) =>
      (laps.dataByEntryId[entry.id] ?? [])
        .filter(
          (lap) =>
            workspace.lapSelection === "all" ||
            lap.lap_number === workspace.lapSelection,
        )
        .map((lap) => ({
          id: `${entry.id}-${lap.id}`,
          driver: getEntryDisplayName(entry),
          accent: getEntryAccent(entry, index),
          lap,
        })),
    )
    .sort((left, right) => right.lap.lap_number - left.lap.lap_number);

  return (
    <WidgetCard
      title={widgetOptions.title ?? "Lap Table"}
      description="Selected-driver lap data for the current workspace filters."
    >
      {rows.length === 0 ? (
        <WidgetEmpty message="No laps matched the current driver and lap selection." />
      ) : (
        <LapRows
          key={`${workspace.sessionId}:${workspace.lapSelection}`}
          rows={rows}
        />
      )}
    </WidgetCard>
  );
}

function LapRows({ rows }: { rows: LapRow[] }) {
  const [requestedPage, setPage] = useState(0);
  const lastPage = Math.ceil(rows.length / LAP_ROWS_PER_PAGE) - 1;
  const page = Math.min(requestedPage, lastPage);
  const start = page * LAP_ROWS_PER_PAGE;
  const end = Math.min(rows.length, start + LAP_ROWS_PER_PAGE);

  return (
    <>
      <div className="lap-table-controls">
        <p aria-live="polite">
          Showing {start + 1}–{end} of {rows.length} lap entries
        </p>
        {lastPage > 0 ? (
          <div className="lap-table-controls__buttons">
            <button
              type="button"
              className="button-secondary"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </button>
            <button
              type="button"
              className="button-secondary"
              disabled={page === lastPage}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        ) : null}
      </div>
      <div className="telemetry-table" role="table" aria-label="Lap data">
        <div
          className="telemetry-table__header telemetry-table__row"
          role="row"
        >
          <span role="columnheader">Driver</span>
          <span role="columnheader">Lap</span>
          <span role="columnheader">Time</span>
          <span role="columnheader">Compound</span>
          <span role="columnheader">Tyre life</span>
        </div>
        {rows.slice(start, end).map((row) => (
          <div key={row.id} className="telemetry-table__row" role="row">
            <span className="telemetry-driver-chip" role="cell">
              <i style={{ backgroundColor: row.accent }} />
              {row.driver}
            </span>
            <span role="cell">L{row.lap.lap_number}</span>
            <span role="cell">{formatLapTime(row.lap.lap_time_ms)}</span>
            <span role="cell">{row.lap.compound ?? "N/A"}</span>
            <span role="cell">{row.lap.tyre_life ?? "N/A"}</span>
          </div>
        ))}
      </div>
    </>
  );
}
