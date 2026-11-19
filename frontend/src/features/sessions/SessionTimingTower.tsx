import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import type { Ref } from "react";
import { driverBadgeColors } from "../../components/driver-select-options";
import type { SessionEntryDto } from "../../data/contracts/sessions.contracts";
import { useSessionTimingTowerQuery } from "../../data/queries/sessions.queries";
import { useReplayTime, useSessionWorkspace } from "./SessionWorkspaceContext";
import { formatLapTime } from "./session-utils";
import { timingHeader, timingRows, type TowerRow } from "./timing-tower-model";
import "./session-timing-tower.css";

const railViewport = "(min-width: 1344px)";
function subscribeToViewport(notify: () => void) {
  const media = matchMedia(railViewport);
  media.addEventListener("change", notify);
  return () => media.removeEventListener("change", notify);
}
const canShowRail = () => matchMedia(railViewport).matches;

const flags: Record<string, [label: string, tone: string]> = {
  GREEN: ["Green flag", "green"],
  YELLOW: ["Yellow flag", "yellow"],
  "DOUBLE YELLOW": ["Double yellow", "yellow"],
  "LOCAL YELLOW": ["Local yellow", "yellow"],
  "LOCAL DOUBLE YELLOW": ["Local double yellow", "yellow"],
  "LOCAL RED": ["Local red flag", "red"],
  RED: ["Red flag", "red"],
  "SAFETY CAR": ["Safety car", "yellow"],
  "VIRTUAL SAFETY CAR": ["Virtual safety car", "yellow"],
  "VSC ENDING": ["VSC ending", "yellow"],
  CHEQUERED: ["Chequered flag", "finished"],
};

type Comparison = "gap" | "interval";
type Flag = { label: string; tone: string; sectors: number[] };
type Mode = ReturnType<typeof useSessionWorkspace>["mode"];
type TowerContentProps = {
  summary: string;
  flag?: Flag;
  comparison: Comparison;
  setComparison: (value: Comparison) => void;
  query: ReturnType<typeof useSessionTimingTowerQuery>;
  entries: SessionEntryDto[];
  mode: Mode;
  time: number;
};

export function SessionTimingTower() {
  const { sessionId, mode, entries } = useSessionWorkspace();
  const time = useReplayTime();
  const wide = useSyncExternalStore(subscribeToViewport, canShowRail);
  const [expanded, setExpanded] = useState(true);
  const [comparison, setComparison] = useState<Comparison>("gap");
  const nextFocus = useRef<"dock" | "rail" | null>(null);
  const desktopButton = useRef<HTMLButtonElement>(null);
  useLayoutEffect(() => {
    if (wide && nextFocus.current)
      desktopButton.current?.focus({ preventScroll: true });
    nextFocus.current = null;
  }, [wide, expanded]);
  const query = useSessionTimingTowerQuery(sessionId);
  const header = timingHeader(query.data, time, mode);
  const flagLabel = flags[header.flag ?? ""];
  const flag = flagLabel && {
    label: flagLabel[0],
    tone: flagLabel[1],
    sectors: header.sectors,
  };
  const race = query.data?.kind === "race";
  const showDistance =
    mode === "simulation" && header.flag !== "CHEQUERED" && header.total;
  const progress =
    race && header.lap
      ? `Lap ${header.lap}${showDistance ? ` / ${header.total}` : ""}`
      : null;
  const summary =
    progress ??
    (mode === "lookback"
      ? "Results"
      : query.data?.kind === "timed"
        ? "Session best"
        : "Replay");
  const props = {
    summary,
    flag,
    comparison,
    setComparison,
    query,
    time,
    entries,
    mode,
  };
  if (wide)
    return expanded ? (
      <aside
        className="session-timing session-timing-rail"
        aria-labelledby="session-timing-title"
      >
        <TowerContent
          {...props}
          desktop
          closeRef={desktopButton}
          close={() => {
            nextFocus.current = "dock";
            setExpanded(false);
          }}
        />
      </aside>
    ) : (
      <DockButton
        summary={summary}
        flag={flag}
        buttonRef={desktopButton}
        onClick={() => {
          nextFocus.current = "rail";
          setExpanded(true);
        }}
      />
    );
  return <TimingSheet {...props} />;
}

function TowerContent({
  summary,
  flag,
  comparison,
  setComparison,
  desktop,
  closeRef,
  close,
  ...timing
}: TowerContentProps & {
  desktop?: boolean;
  closeRef?: Ref<HTMLButtonElement>;
  close: () => void;
}) {
  return (
    <>
      <header className="session-timing__head">
        <div className="session-timing__title-line">
          <h2 id="session-timing-title">Timing tower</h2>
          <button
            ref={closeRef}
            className="session-timing__close"
            type="button"
            onClick={close}
            aria-label={
              desktop ? "Collapse timing tower" : "Close timing tower"
            }
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              aria-hidden="true"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
            >
              {desktop ? (
                <path d="m5 3 5 5-5 5" />
              ) : (
                <path d="m4 4 8 8m0-8-8 8" />
              )}
            </svg>
          </button>
        </div>
        <div className="session-timing__context">
          <span>{summary}</span>
          {flag && (
            <span
              className="session-timing__flag"
              data-tone={flag.tone}
              title={
                flag.sectors.length
                  ? `Marshal sectors ${flag.sectors.join(", ")}`
                  : undefined
              }
            >
              {flag.label}
            </span>
          )}
        </div>
      </header>
      {timing.query.data?.kind === "race" && (
        <div
          className="session-timing__comparison"
          role="group"
          aria-label="Compare timing"
        >
          <button
            type="button"
            aria-pressed={comparison === "gap"}
            onClick={() => setComparison("gap")}
          >
            To leader
          </button>
          <button
            type="button"
            aria-pressed={comparison === "interval"}
            onClick={() => setComparison("interval")}
          >
            Interval
          </button>
        </div>
      )}
      <TimingTable comparison={comparison} {...timing} />
    </>
  );
}

function DockButton({
  summary,
  flag,
  onClick,
  buttonRef,
  controls,
  expanded,
}: {
  summary: string;
  flag?: Flag;
  onClick: () => void;
  buttonRef?: Ref<HTMLButtonElement>;
  controls?: string;
  expanded?: boolean;
}) {
  return (
    <button
      ref={buttonRef}
      type="button"
      className="session-timing-dock"
      onClick={onClick}
      aria-label="Open timing tower"
      aria-description={[summary, flag?.label].filter(Boolean).join(", ")}
      aria-expanded={expanded}
      aria-controls={controls}
      aria-haspopup={controls ? "dialog" : undefined}
    >
      <svg
        width="17"
        height="17"
        viewBox="0 0 17 17"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        aria-hidden="true"
      >
        <path d="M2 4h2m2 0h9M2 8.5h2m2 0h9M2 13h2m2 0h9" />
      </svg>
      <b>Timing</b>
      <span>{summary}</span>
      {flag && (
        <i
          className="session-timing__flag"
          data-tone={flag.tone}
          title={flag.label}
          aria-hidden="true"
        />
      )}
    </button>
  );
}

function TimingSheet(props: TowerContentProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const dock = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  useLayoutEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal();
  }, [open]);
  return (
    <>
      <DockButton
        summary={props.summary}
        flag={props.flag}
        buttonRef={dock}
        expanded={open}
        controls="session-timing-sheet"
        onClick={() => setOpen(true)}
      />
      <dialog
        id="session-timing-sheet"
        ref={dialog}
        className="session-timing session-timing-sheet"
        aria-labelledby="session-timing-title"
        onClose={() => {
          setOpen(false);
          dock.current?.focus();
        }}
        onClick={(event) => {
          if (event.target === event.currentTarget) {
            const bounds = event.currentTarget.getBoundingClientRect();
            if (
              event.clientY < bounds.top ||
              event.clientY > bounds.bottom ||
              event.clientX < bounds.left ||
              event.clientX > bounds.right
            )
              dialog.current?.close();
          }
        }}
      >
        {open && (
          <TowerContent {...props} close={() => dialog.current?.close()} />
        )}
      </dialog>
    </>
  );
}

function TimingTable({
  comparison,
  entries,
  mode,
  time,
  query,
}: Pick<
  TowerContentProps,
  "comparison" | "entries" | "mode" | "time" | "query"
>) {
  const { data, isPending, isError, refetch } = query;
  const cutoff = mode === "lookback" ? Infinity : time;
  const rows = useMemo(
    () => (data ? timingRows(data, entries, cutoff, mode) : []),
    [data, entries, cutoff, mode],
  );
  const race = data?.kind === "race";
  const heading = race
    ? comparison === "gap"
      ? "Gap to leader"
      : "Car ahead"
    : "Best lap";
  const showNote =
    race &&
    mode === "simulation" &&
    rows.some((row) => row.source === "line" && row[comparison] != null);

  if (isPending)
    return (
      <p className="session-timing__message" role="status">
        Loading timing…
      </p>
    );
  if (!data && isError)
    return (
      <div className="session-timing__message">
        Timing couldn’t load.{" "}
        <button type="button" onClick={() => void refetch()}>
          Retry
        </button>
      </div>
    );
  if (!rows.length)
    return <p className="session-timing__message">No drivers are available.</p>;
  return (
    <>
      <div
        className="session-timing__scroll"
        tabIndex={0}
        role="region"
        aria-label="Full-field standings"
      >
        <table
          className="session-timing__table"
          aria-label={
            mode === "lookback"
              ? "Session classification"
              : race
                ? "Running order"
                : "Session best laps"
          }
        >
          <thead>
            <tr>
              <th scope="col">Pos</th>
              <th scope="col">Driver</th>
              <th scope="col">{heading}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <TimingRow
                key={row.entry.id}
                row={row}
                race={race}
                comparison={comparison}
              />
            ))}
          </tbody>
        </table>
      </div>
      {race && mode === "simulation" && (
        <p
          className="session-timing__note"
          data-visible={showNote}
          aria-hidden={!showNote}
        >
          * Last shared timing line
        </p>
      )}
    </>
  );
}

function TimingRow({
  row,
  race,
  comparison,
}: {
  row: TowerRow;
  race: boolean;
  comparison: Comparison;
}) {
  const entry = row.entry;
  const { background } = driverBadgeColors(entry.team_color);
  const value = race ? row[comparison] : row.time;
  const delta =
    value == null
      ? "—"
      : value < 0
        ? `+${-value} ${value === -1 ? "lap" : "laps"}`
        : `+${(value / 1000).toFixed(3)} s`;
  const displayed = race
    ? (row.status ?? (row.position === 1 ? "Leader" : delta))
    : value == null
      ? "—"
      : formatLapTime(value);
  return (
    <tr data-position={row.position ?? undefined}>
      <td>{row.position ?? "—"}</td>
      <th scope="row" title={entry.driver_name ?? undefined}>
        <span className="session-timing__driver">
          <i style={{ background }} aria-hidden="true" />
          <b aria-label={entry.driver_name ?? undefined}>
            {entry.driver_abbreviation ?? `#${entry.car_number}`}
          </b>
          {entry.driver_abbreviation && <small>{entry.car_number}</small>}
        </span>
      </th>
      <td data-missing={displayed === "—"}>
        {displayed}
        {race && row.source === "line" && value != null ? (
          <sup title="Gap at last shared timing line">*</sup>
        ) : null}
      </td>
    </tr>
  );
}
