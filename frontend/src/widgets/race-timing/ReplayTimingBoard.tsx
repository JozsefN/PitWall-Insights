import { useMemo } from "react";
import { driverBadgeColors } from "../../components/driver-select-options";
import {
  useReplayTime,
  useSessionWorkspace,
} from "../../features/sessions/SessionWorkspaceContext";
import {
  formatLapTime,
  getEntryDisplayName,
} from "../../features/sessions/session-utils";
import { useWorkspaceReplayData } from "../../features/sessions/workspace-replay-data";
import { snapshotCutoff } from "../../features/race-insights/presentation";
import { WidgetCard } from "../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../shared/WidgetState";
import { rankedTimedLaps } from "./replay-timed-laps";
import "./timing-panels.css";

export function ReplayTimingBoard({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const { selectedEntries, selectedDriverIds } = useSessionWorkspace();
  const time = snapshotCutoff(useReplayTime("review"));
  const laps = useWorkspaceReplayData().laps;
  const rows = useMemo(
    () => rankedTimedLaps(laps.dataByEntryId, selectedDriverIds, time),
    [laps.dataByEntryId, selectedDriverIds, time],
  );
  const entries = new Map(selectedEntries.map((entry) => [entry.id, entry]));
  const fastest = rows[0];
  return (
    <WidgetCard
      title={
        typeof options?.title === "string"
          ? options.title
          : "Replay timing board"
      }
      description="Best completed lap per selected driver. Sector differences in seconds use the leading lap."
    >
      {laps.isError ? (
        <WidgetError />
      ) : laps.isLoading ? (
        <WidgetLoading />
      ) : !fastest ? (
        <WidgetEmpty
          message={
            selectedEntries.length
              ? "Waiting for a valid completed lap."
              : "Choose drivers to follow their lap times."
          }
        />
      ) : (
        <div className="timing-board-scroll">
          <table className="timing-board">
            <thead>
              <tr>
                <th scope="col">Driver</th>
                <th scope="col">Best lap</th>
                <th scope="col">Gap</th>
                <th scope="col">S1</th>
                <th scope="col">S2</th>
                <th scope="col">S3</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ id, lap, time }, index) => {
                const entry = entries.get(id);
                return (
                  <tr
                    key={id}
                    data-lap={lap.lap_number}
                    data-entry={id}
                    data-leading={!index}
                  >
                    <th scope="row">
                      <span>{index + 1}</span>{" "}
                      {entry ? (
                        <b
                          className="timing-board-driver"
                          style={driverBadgeColors(entry.team_color)}
                          title={entry.driver_name ?? undefined}
                        >
                          {getEntryDisplayName(entry)}
                        </b>
                      ) : (
                        "Driver"
                      )}
                    </th>
                    <td title={`Lap ${lap.lap_number}`}>
                      {formatLapTime(time)}
                    </td>
                    <td>{index ? displayDelta(time, fastest.time) : "Best"}</td>
                    {(
                      [
                        "sector_1_time_ms",
                        "sector_2_time_ms",
                        "sector_3_time_ms",
                      ] as const
                    ).map((key) => (
                      <td
                        key={key}
                        data-faster={
                          lap[key] != null &&
                          fastest.lap[key] != null &&
                          lap[key] < fastest.lap[key]
                        }
                      >
                        {displayDelta(lap[key], fastest.lap[key])}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </WidgetCard>
  );
}

function displayDelta(value: number | null, reference: number | null) {
  if (value == null || reference == null) return "—";
  const delta = (value - reference) / 1000;
  return `${delta > 0 ? "+" : ""}${delta.toFixed(3)}`;
}
