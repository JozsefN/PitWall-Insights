import type { SessionEntryDto } from "../../data/contracts/sessions.contracts.ts";
import type { TimingTowerDto } from "../../data/contracts/session-timing.contracts.ts";

type Crossing = TimingTowerDto["race_laps"][string][number];
type Mode = "simulation" | "lookback";
export type TowerRow = {
  entry: SessionEntryDto;
  position: number | null;
  lastCrossing?: Crossing;
  time: number | null;
  gap: number | null;
  interval: number | null;
  source?: "reported" | "line";
  status?: string;
};

const gapExpiryMs = 15_000;
const crossingExpiryMs = 150_000;

function at<T extends readonly [number, ...unknown[]]>(
  series: readonly T[] | undefined,
  time: number,
) {
  if (!series) return undefined;
  let lo = 0;
  let hi = series.length;
  while (lo < hi) {
    const mid = (lo + hi) >>> 1;
    if (series[mid][0] <= time) lo = mid + 1;
    else hi = mid;
  }
  return series[lo - 1];
}

export function timingHeader(
  data: TimingTowerDto | undefined,
  cutoff: number,
  mode: Mode,
) {
  const time = mode === "lookback" ? Infinity : cutoff;
  const [, flag, sectors = []] = at(data?.flags, time) ?? [];
  const [, completed = 0] = at(data?.race_crossings, time) ?? [];
  const total =
    mode === "lookback" && completed ? completed : data?.scheduled_laps;
  const lap =
    mode === "lookback" || flag === "CHEQUERED"
      ? completed
      : Math.min(completed + 1, total ?? Infinity);
  return { flag, sectors, lap, total };
}

function timedRows(
  data: TimingTowerDto,
  entries: readonly SessionEntryDto[],
  time: number,
  final: boolean,
): TowerRow[] {
  const rows = entries.map((entry) => {
    let best = final
      ? (data.best_laps[entry.car_number] ?? Infinity)
      : Infinity;
    let setAt = Infinity;
    if (!final)
      for (const [stamp, lap, decisions] of data.timed_laps[entry.car_number] ??
        []) {
        if (stamp > time) break;
        if (lap >= best || at(decisions, time)?.[1] === false) continue;
        best = lap;
        setAt = stamp;
      }
    const position = final
      ? (entry.result_position ?? entry.classified_position)
      : null;
    return {
      entry,
      position,
      time: Number.isFinite(best) ? best : null,
      gap: null,
      interval: null,
      setAt,
    };
  });
  const hasClassification = final && rows.some((row) => row.position != null);
  rows.sort((a, b) =>
    hasClassification
      ? rankOrder(a, b)
      : rank(a.time) - rank(b.time) || a.setAt - b.setAt || carOrder(a, b),
  );
  if (!hasClassification)
    rows.forEach((row, index) => {
      row.position = row.time == null ? null : index + 1;
    });
  return rows;
}

const rank = (value: number | null) => value ?? Infinity;
const carOrder = (a: TowerRow, b: TowerRow) =>
  Number(a.entry.car_number) - Number(b.entry.car_number);
const rankOrder = (a: TowerRow, b: TowerRow) =>
  rank(a.position) - rank(b.position) || carOrder(a, b);

function crossingGap(
  data: TimingTowerDto,
  row: TowerRow,
  reference: TowerRow | undefined,
  time: number,
) {
  if (
    !reference ||
    time - (row.lastCrossing?.[0] ?? -Infinity) > crossingExpiryMs ||
    !row.lastCrossing
  )
    return null;
  const [stamp, lap] = row.lastCrossing;
  const crossing = (data.race_laps[reference.entry.car_number] ?? []).find(
    ([pt, pn]) => pn === lap && pt <= time,
  );
  if (!crossing) return null;
  const delta = stamp - crossing[0];
  return delta >= 0 && delta <= crossingExpiryMs ? delta : null;
}

function raceRows(
  data: TimingTowerDto,
  entries: readonly SessionEntryDto[],
  time: number,
  final: boolean,
): TowerRow[] {
  const claimed = new Set<number>();
  const onGrid = !at(data.race_crossings, time);
  const rows = entries
    .map((entry) => {
      const lastCrossing = at(data.race_laps[entry.car_number], time);
      const report = at(data.ranks[entry.car_number], time);
      const position = final
        ? (entry.result_position ??
          entry.classified_position ??
          report?.[1] ??
          lastCrossing?.[2] ??
          null)
        : (report?.[1] ??
          lastCrossing?.[2] ??
          (onGrid && entry.grid_position && entry.grid_position > 0
            ? entry.grid_position
            : null));
      return {
        entry,
        position,
        lastCrossing,
        reportedAt: report?.[0] ?? lastCrossing?.[0] ?? -Infinity,
        time: null,
        gap: null,
        interval: null,
      };
    })
    .sort(
      (a, b) =>
        rank(a.position) - rank(b.position) ||
        b.reportedAt - a.reportedAt ||
        carOrder(a, b),
    );

  // Position reports for a pass may arrive one car at a time. Show a single claim for each place.
  for (const row of rows) {
    if (row.position == null) continue;
    if (claimed.has(row.position)) row.position = null;
    else claimed.add(row.position);
  }
  rows.sort(rankOrder);
  const leader = rows.find((row) => row.position === 1);
  const statuses: Record<string, string> = {
    retired: "DNF",
    "did not start": "DNS",
    disqualified: "DSQ",
  };
  return rows.map((row, index) => {
    const status = final
      ? statuses[row.entry.status?.toLowerCase() ?? ""]
      : undefined;
    if (row.position == null || status) return { ...row, status };
    if (row.position === 1) return { ...row, gap: 0, interval: 0 };
    const previous = rows[index - 1];
    const ahead =
      previous?.position === row.position - 1 &&
      (!final || !statuses[previous.entry.status?.toLowerCase() ?? ""])
        ? previous
        : undefined;
    const car = row.entry.car_number;
    if (!final) {
      const report = at(data.gaps[car], time);
      if (report && time - report[0] <= gapExpiryMs)
        return {
          ...row,
          gap: report[1],
          interval: report[2],
          source: "reported",
        };
      return {
        ...row,
        gap: crossingGap(data, row, leader, time),
        interval: crossingGap(data, row, ahead, time),
        source: "line",
      };
    }
    return {
      ...row,
      gap: finishGap(data, row, leader),
      interval: finishGap(data, row, ahead),
      source: "reported",
    };
  });
}

function finishGap(
  data: TimingTowerDto,
  row: TowerRow,
  reference: TowerRow | undefined,
) {
  if (!reference) return null;
  const own = data.classified_gaps[row.entry.car_number];
  const peer =
    reference.position === 1
      ? 0
      : data.classified_gaps[reference.entry.car_number];
  if (own != null && peer != null) {
    if (own < 0 || peer < 0) return own < peer ? own - Math.min(0, peer) : null;
    return own >= peer ? own - peer : null;
  }
  const laps = row.entry.laps_completed ?? row.lastCrossing?.[1];
  const aheadLaps =
    reference.entry.laps_completed ?? reference.lastCrossing?.[1];
  if (laps == null || aheadLaps == null) return null;
  if (aheadLaps > laps) return laps - aheadLaps;
  if (
    aheadLaps !== laps ||
    row.lastCrossing?.[1] !== laps ||
    reference.lastCrossing?.[1] !== laps
  )
    return null;
  const delta = row.lastCrossing[0] - reference.lastCrossing[0];
  return delta >= 0 ? delta : null;
}

export function timingRows(
  data: TimingTowerDto,
  entries: readonly SessionEntryDto[],
  cutoff: number,
  mode: Mode,
) {
  const final = mode === "lookback";
  const time = final ? Infinity : cutoff;
  return data.kind === "race"
    ? raceRows(data, entries, time, final)
    : timedRows(data, entries, time, final);
}
