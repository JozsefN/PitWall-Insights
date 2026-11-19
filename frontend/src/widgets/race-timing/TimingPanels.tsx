import { useMemo, useState, type CSSProperties } from "react";
import type {
  EntryLapDto,
  SessionEntryDto,
} from "../../data/contracts/sessions.contracts";
import { useWorkspaceEntryLapsResource } from "../../features/sessions/session-data.hooks";
import {
  useReplayTime,
  useSessionWorkspace,
} from "../../features/sessions/SessionWorkspaceContext";
import {
  getEntryAccent,
  getEntryDisplayName,
} from "../../features/sessions/session-utils";
import { useWorkspaceReplayData } from "../../features/sessions/workspace-replay-data";
import { WidgetCard } from "../shared/WidgetCard";
import { WidgetEmpty, WidgetError, WidgetLoading } from "../shared/WidgetState";
import { useWidgetSize } from "../shared/widget-size";
import { ChartDriverPicker } from "../telemetry/components/ChartDriverPicker";
import {
  getCompoundColor,
  getCompoundLabel,
  getCompoundShortLabel,
} from "../telemetry/utils/stint-analysis";
import { lapAxis, lapPositions, tyreRuns } from "./timing-data";
import "./timing-panels.css";

type PanelOptions = { options?: Record<string, unknown> };
type Rows = { entry: SessionEntryDto; laps: EntryLapDto[] }[];
export function TyreTimelineWidget(props: PanelOptions) {
  return <TimingPanel {...props} kind="tyres" />;
}

export function PositionHistoryWidget(props: PanelOptions) {
  return <TimingPanel {...props} kind="position" />;
}

function TimingPanel({
  kind,
  options,
}: PanelOptions & { kind: "tyres" | "position" }) {
  const workspace = useSessionWorkspace();
  const replay = workspace.mode === "simulation";
  const replayLaps = useWorkspaceReplayData().laps;
  const lookback = useWorkspaceEntryLapsResource({
    entryMode: "selected",
    enabled: !replay && workspace.selectedEntries.length > 0,
  });
  const time = useReplayTime("review");
  const cutoff = replay ? time : undefined;
  const resource = replay ? replayLaps : lookback;
  const [driver, setDriver] = useState("");
  const focus = workspace.selectedEntries.some(({ id }) => id === driver)
    ? driver
    : "";
  const entries = workspace.selectedEntries;
  const rows = useMemo(
    () =>
      entries.map((entry) => ({
        entry,
        laps: resource.dataByEntryId[entry.id] ?? [],
      })),
    [entries, resource.dataByEntryId],
  );
  const title =
    typeof options?.title === "string"
      ? options.title
      : kind === "tyres"
        ? "Tyre timeline"
        : "Position history";
  return (
    <WidgetCard
      title={title}
      description={
        kind === "tyres"
          ? "Compound changes by lap. Select a driver to inspect their sets."
          : "Running position at each driver's lap completion."
      }
      actions={
        <ChartDriverPicker
          drivers={entries.map((entry) => ({
            entry,
            id: entry.id,
            label: getEntryDisplayName(entry),
          }))}
          value={focus}
          onChange={setDriver}
        />
      }
    >
      {!entries.length ? (
        <WidgetEmpty message="Choose drivers to compare their session history." />
      ) : resource.isError ? (
        <WidgetError />
      ) : resource.isLoading ? (
        <WidgetLoading />
      ) : kind === "tyres" ? (
        <TyreTimeline rows={rows} focus={focus} cutoff={cutoff} />
      ) : (
        <PositionHistory
          rows={rows}
          focus={focus}
          cutoff={cutoff}
          fieldSize={workspace.entries.length}
        />
      )}
    </WidgetCard>
  );
}

function TyreTimeline({
  rows,
  focus,
  cutoff,
}: {
  rows: Rows;
  focus: string;
  cutoff?: number;
}) {
  const series = useMemo(
    () =>
      rows.map(({ entry, laps }) => ({ entry, runs: tyreRuns(laps, cutoff) })),
    [rows, cutoff],
  );
  const axis = lapAxis(
    Math.max(0, ...series.map(({ runs }) => runs.at(-1)?.to ?? 0)),
  );
  const visible = series.filter(({ entry }) => !focus || entry.id === focus);
  const compounds = [
    ...new Set(
      visible.flatMap(({ runs }) => runs.map(({ compound }) => compound)),
    ),
  ];
  if (!compounds.length)
    return (
      <WidgetEmpty message="Tyre records appear after a recorded lap is completed." />
    );
  return (
    <div className="timing-panel">
      <div className="timing-legend timing-legend--compound">
        {compounds.map((compound) => (
          <span key={compound ?? "unknown"}>
            <i style={{ background: getCompoundColor(compound) }} />
            {getCompoundLabel(compound)}
          </span>
        ))}
      </div>
      <div className="tyre-axis" aria-hidden="true">
        <span>Lap</span>
        <div>
          {axis.ticks.map((tick) => (
            <span key={tick} style={{ left: `${(100 * tick) / axis.end}%` }}>
              {tick}
            </span>
          ))}
        </div>
      </div>
      <ul
        className="tyre-timeline"
        aria-label="Tyre compound history by driver"
        style={{ "--lap-grid": `${(100 * axis.step) / axis.end}%` } as CSSProperties}
      >
        {visible.map(({ entry, runs }) => (
          <li key={entry.id} className="tyre-row" data-entry-id={entry.id}>
            <strong
              title={entry.driver_name ?? undefined}
              style={
                { "--timing-accent": getEntryAccent(entry) } as CSSProperties
              }
            >
              {getEntryDisplayName(entry)}
            </strong>
            <div
              className="tyre-row__track"
              aria-label={
                runs.length ? "Recorded tyre sets" : "Tyre records unavailable"
              }
            >
              {runs.map((run) => {
                const { compound, from, to, lastCompletedAge } = run;
                const width = ((to - from + 1) / axis.end) * 100;
                const note = `${getCompoundLabel(compound)} · Lap ${from}${to === from ? "" : `–${to}`}${lastCompletedAge == null ? "" : ` · Age at last completed lap ${lastCompletedAge} laps`}`;
                return (
                  <span
                    key={from}
                    className="tyre-row__stint"
                    title={note}
                    aria-label={note}
                    data-last-lap={to}
                    style={
                      {
                        left: `${((from - 1) / axis.end) * 100}%`,
                        width: `${width}%`,
                        "--compound": getCompoundColor(compound),
                      } as CSSProperties
                    }
                  >
                    {width > 7 ? getCompoundShortLabel(compound) : ""}
                  </span>
                );
              })}
            </div>
          </li>
        ))}
      </ul>
      {focus && visible[0]?.runs.length ? (
        <ul className="timing-details" aria-label="Selected driver's tyre sets">
          {visible[0].runs.map((run) => (
            <li key={run.from}>
              <strong>{getCompoundLabel(run.compound)}</strong>
              <span>
                Lap {run.from}
                {run.to === run.from ? "" : `–${run.to}`}
              </span>
              {run.lastCompletedAge != null ? (
                <span>{run.lastCompletedAge} laps old at last completion</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function PositionHistory({
  rows,
  focus,
  cutoff,
  fieldSize,
}: {
  rows: Rows;
  focus: string;
  cutoff?: number;
  fieldSize: number;
}) {
  const { width } = useWidgetSize();
  const chartWidth = Math.max(240, width ? width - 48 : 440);
  const series = useMemo(
    () =>
      rows.map(({ entry, laps }) => ({
        entry,
        points: lapPositions(laps, cutoff),
      })),
    [rows, cutoff],
  );
  const populated = series.filter(({ points }) => points.length);
  const axis = lapAxis(
    Math.max(0, ...populated.map(({ points }) => points.at(-1)!.lap)),
  );
  const bottom = Math.max(
    2,
    fieldSize,
    ...populated.flatMap(({ points }) =>
      points.map(({ position }) => position),
    ),
  );
  const rankTicks = [
    ...new Set([1, ...[5, 10, 15, 20].filter((p) => p < bottom), bottom]),
  ];
  const left = 36,
    right = chartWidth - 16,
    top = 14,
    floor = 181;
  const x = (lap: number) => left + (lap / axis.end) * (right - left);
  const y = (rank: number) => top + ((rank - 1) / (bottom - 1)) * (floor - top);
  const focused = populated.find(({ entry }) => entry.id === focus);
  if (!populated.length)
    return (
      <WidgetEmpty message="Positions appear after the first recorded lap is completed." />
    );

  return (
    <div className="timing-panel">
      <svg
        className="timing-plot"
        role="img"
        aria-label="Running order by completed lap. First position is at the top."
        viewBox={`0 0 ${chartWidth} 216`}
      >
        {rankTicks.map((rank) => (
          <g key={rank}>
            <text x={left - 8} y={y(rank) + 4} textAnchor="end">
              P{rank}
            </text>
            <path
              d={`M${left} ${y(rank)}H${right}`}
              className="timing-plot__grid"
            />
          </g>
        ))}
        {axis.ticks.map((lap) => (
          <text key={lap} x={x(lap)} y={floor + 19} textAnchor="middle">
            {lap}
          </text>
        ))}
        <text x={left} y={floor + 19} textAnchor="middle">
          Lap
        </text>
        {[
          ...populated.filter(({ entry }) => entry.id !== focus),
          ...(focused ? [focused] : []),
        ].map(({ entry, points }) => {
          const active = !focus || focus === entry.id;
          const path = points
            .map((point, i) => {
              const prev = points[i - 1];
              return prev?.lap === point.lap - 1
                ? `H${x(point.lap)}V${y(point.position)}`
                : `M${x(point.lap)} ${y(point.position)}`;
            })
            .join(" ");
          const last = points.at(-1)!;
          return (
            <g
              key={entry.id}
              data-entry-id={entry.id}
              data-last-lap={last.lap}
              data-emphasis={active}
              style={
                { "--timing-accent": getEntryAccent(entry) } as CSSProperties
              }
            >
              <path d={path} className="timing-plot__series" />
              <circle
                cx={x(last.lap)}
                cy={y(last.position)}
                r={active ? 3.4 : 2.1}
              >
                <title>
                  {getEntryDisplayName(entry)} · P{last.position} after lap{" "}
                  {last.lap}
                </title>
              </circle>
            </g>
          );
        })}
      </svg>
      <div className="timing-legend" aria-label="Latest recorded positions">
        {focused ? (
          positionLabel(focused.entry, focused.points)
        ) : focus ? (
          <span>No positions recorded for this driver.</span>
        ) : (
          populated.map(({ entry, points }) => positionLabel(entry, points))
        )}
      </div>
    </div>
  );
}

function positionLabel(
  entry: SessionEntryDto,
  points: ReturnType<typeof lapPositions>,
) {
  const last = points.at(-1)!;
  const move = points[0].position - last.position;
  const trend = move ? `${move > 0 ? "↑" : "↓"}${Math.abs(move)}` : "";
  return (
    <span
      key={entry.id}
      title={`P${last.position} after lap ${last.lap}. Change from first recorded position.`}
    >
      <i style={{ background: getEntryAccent(entry) }} />
      <strong>{getEntryDisplayName(entry)}</strong> P{last.position} {trend}
    </span>
  );
}
