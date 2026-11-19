import { DriverSelect } from "../../components/DriverSelect";
import { driverOption } from "../../components/driver-select-options";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState, type CSSProperties } from "react";
import { apiClient } from "../../data/api/client";
import { useTelemetryMaterializationReadiness } from "../../features/sessions/session-data.hooks";
import { useSessionWorkspace } from "../../features/sessions/SessionWorkspaceContext";
import {
  formatLapTime,
  getEntryAccent,
  getEntryDisplayName,
} from "../../features/sessions/session-utils";
import { WidgetCard } from "../shared/WidgetCard";
import {
  buildTrackBounds,
  buildPaddedBaseViewBox,
} from "../track-map/utils/geometry";
import { smoothTrackPath } from "../track-map/utils/track-curves";
import "./qualifying-lap.css";

type Point = [number, number];
type Choice = { entry_id: string; lap_number: number };
type Lap = Choice & { lap_time_ms: number };
type Ranking = Choice & {
  time_ms: number;
  delta_ms: number;
  delta_to_focus_ms: number | null;
};
type Split = {
  number: number;
  focus_ms: number | null;
  focus_delta_ms: number | null;
  colour: "purple" | "green" | "yellow" | "unknown";
  path: Point[];
  ranking: Ranking[];
};
type LapMap = {
  focus: Choice | null;
  laps: Lap[];
  outline?: Point[];
  sectors?: Split[];
  minisectors?: Split[];
  field_driver_count: number;
  minisector_driver_count?: number;
  minisector_lap_count?: number;
  focus_minisectors_available?: boolean;
};

function deltaLabel(value: number | null, estimated: boolean) {
  return value == null
    ? "—"
    : `${value >= 0 ? "+" : "−"}${(Math.abs(value) / 1000).toFixed(estimated ? 2 : 3)} s`;
}

function splitTime(value: number | null, estimated: boolean) {
  return value == null ? "—" : `${(value / 1000).toFixed(estimated ? 2 : 3)} s`;
}

export function QualifyingLapWidget({
  options,
}: {
  options?: Record<string, unknown>;
}) {
  const { sessionId, entries, qualifyingLap: choice, selectQualifyingLap: setChoice } = useSessionWorkspace();
  const [mini, setMini] = useState(false);
  const [number, setNumber] = useState(1);
  const [missingShape, setMissingShape] = useState<Choice>();
  const fieldIds = entries.map((entry) => entry.id);
  const field = useTelemetryMaterializationReadiness({
    entryIds: fieldIds,
    scope: "session",
    kind: "position",
    enabled: mini && fieldIds.length > 0,
  });
  const current = choice ?? missingShape;
  const shape = useTelemetryMaterializationReadiness({
    entryIds: current ? [current.entry_id] : [],
    scope: "lap",
    lapNumber: current?.lap_number,
    kind: "position",
    enabled: Boolean(
      current &&
      missingShape &&
      current.entry_id === missingShape.entry_id &&
      current.lap_number === missingShape.lap_number &&
      !mini,
    ),
  });
  const query = useQuery({
    queryKey: [
      "sessions",
      sessionId,
      "qualifying-lap",
      choice,
      mini,
      mini ? field.ready : shape.ready,
    ],
    queryFn: async ({ signal }) =>
      (
        await apiClient.get<LapMap>(
          `/api/feature-metrics/sessions/${sessionId}/qualifying-lap`,
          {
            params: { ...choice, minisectors: mini },
            signal,
          },
        )
      ).data,
    enabled: !mini || field.ready || field.isError,
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === sessionId ? previous : undefined,
    staleTime: 60_000,
  });
  const data = query.data;
  const focus = choice ?? data?.focus;
  const updatingLap = query.isPlaceholderData && choice && (
    choice.entry_id !== data?.focus?.entry_id ||
    choice.lap_number !== data?.focus?.lap_number
  );
  const eligibleDrivers = new Set(data?.laps.map((lap) => lap.entry_id));
  const driverLaps =
    data?.laps.filter((lap) => lap.entry_id === focus?.entry_id) ?? [];
  const splits = (mini ? data?.minisectors : data?.sectors) ?? [];
  const selected = splits.find((split) => split.number === number);
  const outline = data?.outline;
  const geometry = useMemo(() => {
    if (!outline?.length) return undefined;
    const points = outline.map(([x, y]) => ({ x, y }));
    const box = buildPaddedBaseViewBox(buildTrackBounds(points));
    return {
      viewBox: `${box.minX} ${box.minY} ${box.width} ${box.height}`,
      path: smoothTrackPath(points, true, 8),
    };
  }, [outline]);
  const names = new Map(entries.map((entry) => [entry.id, entry]));
  const name = (id: string) => {
    const driver = names.get(id);
    return driver ? getEntryDisplayName(driver) : "Driver";
  };
  const splitLabel = mini ? "Minisector" : "Sector";
  const title =
    typeof options?.title === "string" ? options.title : "Qualifying Lap Map";
  return (
    <WidgetCard title={title}>
      <div className="qualifying-lap">
        <div className="qualifying-lap__controls">
          <label>
            Driver{" "}
            <DriverSelect
              aria-label="Qualifying lap driver"
              value={focus?.entry_id ?? ""}
              disabled={!eligibleDrivers.size}
              onChange={(value) => {
                const lap = data?.laps.find(
                  (row) => row.entry_id === value,
                );
                if (lap)
                  setChoice({
                    entry_id: lap.entry_id,
                    lap_number: lap.lap_number,
                  });
              }}
              options={entries
                .filter((entry) => eligibleDrivers.has(entry.id))
                .map((entry) => driverOption(entry))}
            />
          </label>
          <label>
            Lap{" "}
            <select
              aria-label="Qualifying timed lap"
              disabled={!driverLaps.length}
              value={focus?.lap_number ?? ""}
              onChange={({ currentTarget }) =>
                focus &&
                setChoice({
                  entry_id: focus.entry_id,
                  lap_number: Number(currentTarget.value),
                })
              }
            >
              {!driverLaps.length ? (
                <option value="">Choose a lap</option>
              ) : null}
              {driverLaps.map((lap) => (
                <option key={lap.lap_number} value={lap.lap_number}>
                  Lap {lap.lap_number} · {formatLapTime(lap.lap_time_ms)}
                </option>
              ))}
            </select>
          </label>
          <div
            className="qualifying-lap__modes"
            role="group"
            aria-label="Timing detail"
          >
            <button
              type="button"
              className="button-secondary"
              aria-pressed={!mini}
              onClick={() => {
                setMini(false);
                setNumber(1);
              }}
            >
              Sectors
            </button>
            <button
              type="button"
              className="button-secondary"
              aria-pressed={mini}
              onClick={() => {
                setMini(true);
                setNumber(1);
              }}
            >
              Minisectors
            </button>
          </div>
        </div>
        {updatingLap ? (
          <p className="qualifying-lap__refresh" role="status">
            {`Loading ${name(choice.entry_id)} lap ${choice.lap_number}. The previous lap is still displayed.`}
          </p>
        ) : null}
        {query.isError ? (
          <div role="alert">
            Lap timing could not be loaded.{" "}
            <button
              type="button"
              className="button-secondary"
              onClick={() => void query.refetch()}
            >
              Retry
            </button>
          </div>
        ) : null}
        {query.isPending ? <p role="status">Loading qualifying laps…</p> : null}
        {data && !data.focus ? (
          <p>No eligible timed laps were recorded in this session.</p>
        ) : null}
        {data?.focus ? (
          <>
            <div className="qualifying-lap__body" aria-busy={Boolean(updatingLap)}>
              <div className="qualifying-lap__map">
                {geometry ? (
                  <svg
                    viewBox={geometry.viewBox}
                    aria-label={`${splitLabel} timing map`}
                    data-qualifying-map
                  >
                    <title>{`${splitLabel} colors for ${name(data.focus.entry_id)}, lap ${data.focus.lap_number}`}</title>
                    <path
                      d={geometry.path}
                      className="qualifying-lap__outline"
                      vectorEffect="non-scaling-stroke"
                    />
                    {splits
                      .filter((split) => split.path.length > 1)
                      .map((split) => {
                        const path = smoothTrackPath(
                          split.path.map(([x, y]) => ({ x, y })),
                          false,
                          8,
                        );
                        return (
                          <g
                            key={split.number}
                            data-split-colour={split.colour}
                            data-current={number === split.number}
                          >
                            <path
                              className="qualifying-lap__split"
                              d={path}
                              vectorEffect="non-scaling-stroke"
                            />
                            <path
                              className="qualifying-lap__hit"
                              d={path}
                              vectorEffect="non-scaling-stroke"
                              onClick={() => setNumber(split.number)}
                              aria-hidden="true"
                            />
                          </g>
                        );
                      })}
                  </svg>
                ) : (
                  <div className="qualifying-lap__map-empty">
                    <p>
                      {shape.isError || field.isError
                        ? "Circuit positions could not be loaded."
                        : shape.isPreparing || field.isPreparing
                          ? "Preparing circuit positions…"
                          : shape.ready || field.ready
                            ? "The available positions do not contain a complete lap outline."
                            : "Circuit positions are needed to draw this lap."}
                    </p>
                    {!mini && !shape.isPreparing && !shape.ready ? (
                      <button
                        type="button"
                        className="button-secondary"
                        onClick={() => focus && setMissingShape(focus)}
                      >
                        Prepare lap map
                      </button>
                    ) : null}
                    {shape.isError ? (
                      <button
                        type="button"
                        className="button-secondary"
                        onClick={() => void shape.retry()}
                      >
                        Retry lap positions
                      </button>
                    ) : null}
                  </div>
                )}
                <div
                  className="qualifying-lap__legend"
                  aria-label="Split colours"
                >
                  <span data-split-colour="purple">Field best</span>
                  <span data-split-colour="green">Personal best</span>
                  <span data-split-colour="yellow">Slower</span>
                  <span data-split-colour="unknown">Missing</span>
                </div>
                <div
                  className="qualifying-lap__splits"
                  role="group"
                  aria-label={`Choose ${splitLabel.toLowerCase()}`}
                >
                  {splits.map((split) => (
                    <button
                      key={split.number}
                      type="button"
                      data-split-colour={split.colour}
                      aria-label={`${splitLabel} ${split.number}`}
                      aria-pressed={split.number === number}
                      onClick={() => setNumber(split.number)}
                    >
                      {split.number}
                    </button>
                  ))}
                </div>
              </div>
              <div className="qualifying-lap__timing">
                <h4>
                  {splitLabel} {number}
                </h4>
                <p>
                  {name(data.focus.entry_id)} · Lap {data.focus.lap_number} ·{" "}
                  <strong>{splitTime(selected?.focus_ms ?? null, mini)}</strong>
                  {selected?.focus_delta_ms != null ? (
                    <> · {deltaLabel(selected.focus_delta_ms, mini)} to best</>
                  ) : null}
                </p>
                <small>
                  {selected?.ranking.length ?? 0} of {data.field_driver_count}{" "}
                  drivers · Best eligible split per driver
                </small>
                {selected?.ranking.length ? (
                  <div className="qualifying-lap__table">
                    <table>
                      <thead>
                        <tr>
                          <th scope="col">Driver</th>
                          <th scope="col">Lap</th>
                          <th scope="col">Time</th>
                          <th scope="col">To best</th>
                          <th scope="col">Vs chosen lap</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selected.ranking.map((row, index) => {
                          const driver = names.get(row.entry_id);
                          return (
                            <tr
                              key={row.entry_id}
                              data-focus-driver={
                                row.entry_id === data.focus?.entry_id
                              }
                            >
                              <th
                                scope="row"
                                style={
                                  driver
                                    ? ({
                                        "--team-colour": getEntryAccent(driver),
                                      } as CSSProperties)
                                    : undefined
                                }
                              >
                                <span>
                                  {selected.ranking.findIndex(
                                    (item) => item.time_ms === row.time_ms,
                                  ) + 1}
                                </span>{" "}
                                {name(row.entry_id)}
                              </th>
                              <td>{row.lap_number}</td>
                              <td>{splitTime(row.time_ms, mini)}</td>
                              <td>
                                {index === 0
                                  ? "Best"
                                  : deltaLabel(row.delta_ms, mini)}
                              </td>
                              <td>{deltaLabel(row.delta_to_focus_ms, mini)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : query.isPlaceholderData && !query.isError ? (
                  <p>
                    {mini && field.isPreparing && !field.isError
                      ? "Waiting for field positions…"
                      : "Loading split times…"}
                  </p>
                ) : (
                  <p>No comparable timing for this split.</p>
                )}
              </div>
            </div>
            {query.isFetching && data && !updatingLap ? (
              <small role="status">Updating timing…</small>
            ) : null}
            {mini ? (
              <p className="qualifying-lap__note">
                Estimated from position samples ·{" "}
                {data.minisector_driver_count ?? 0} of {data.field_driver_count}{" "}
                drivers · {data.minisector_lap_count ?? 0} comparable laps.
                {field.isError
                  ? " Some positions could not be loaded from the source."
                  : field.isPreparing
                    ? " Loading field positions…"
                    : ""}
                {field.ready && data.focus_minisectors_available === false
                  ? " This lap lacks continuous position samples."
                  : ""}
              </p>
            ) : (
              <p className="qualifying-lap__note">
                Reported sector times. Timing-line placement is estimated from
                the reference lap.
              </p>
            )}
            {mini && field.isError ? (
              <button
                type="button"
                className="button-secondary"
                onClick={() => void field.retry()}
              >
                Retry field positions
              </button>
            ) : null}
          </>
        ) : null}
      </div>
    </WidgetCard>
  );
}
