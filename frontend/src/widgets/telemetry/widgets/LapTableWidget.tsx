import { useWorkspaceEntryLapsResource } from "../../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../../features/sessions/SessionWorkspaceContext";
import {
  formatLapTime,
  getEntryAccent,
  getEntryDisplayName,
} from "../../../features/sessions/session-utils";
import { WidgetCard } from "../../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../../shared/WidgetState";
import type { TelemetryWidgetOptions } from "../models";

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
        .filter((lap) => workspace.lapSelection === "all" || lap.lap_number === workspace.lapSelection)
        .map((lap) => ({
          id: `${entry.id}-${lap.id}`,
          driver: getEntryDisplayName(entry),
          accent: getEntryAccent(entry, index),
          lap,
        })),
    )
    .sort((left, right) => right.lap.lap_number - left.lap.lap_number)
    .slice(0, workspace.lapSelection === "all" ? 24 : 12);

  return (
    <WidgetCard
      title={widgetOptions.title ?? "Lap Table"}
      description="Selected-driver lap data for the current workspace filters."
    >
      {rows.length === 0 ? (
        <WidgetEmpty message="No laps matched the current driver and lap selection." />
      ) : (
        <div className="telemetry-table">
          <div className="telemetry-table__header telemetry-table__row">
            <span>Driver</span>
            <span>Lap</span>
            <span>Time</span>
            <span>Compound</span>
            <span>Tyre Life</span>
          </div>
          {rows.map((row) => (
            <div key={row.id} className="telemetry-table__row">
              <span className="telemetry-driver-chip">
                <i style={{ backgroundColor: row.accent }} />
                {row.driver}
              </span>
              <span>L{row.lap.lap_number}</span>
              <span>{formatLapTime(row.lap.lap_time_ms)}</span>
              <span>{row.lap.compound ?? "N/A"}</span>
              <span>{row.lap.tyre_life ?? "N/A"}</span>
            </div>
          ))}
        </div>
      )}
    </WidgetCard>
  );
}
