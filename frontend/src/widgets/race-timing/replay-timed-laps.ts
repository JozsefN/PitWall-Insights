import type { EntryLapDto } from "../../data/contracts/sessions.contracts";

type TimedLap = {
  id: string;
  lap: EntryLapDto;
  time: number;
  completedAt: number;
};

function compareLap(a: TimedLap, b: TimedLap) {
  return (
    a.time - b.time || a.completedAt - b.completedAt || a.id.localeCompare(b.id)
  );
}

export function rankedTimedLaps(
  byEntry: Readonly<Record<string, EntryLapDto[]>>,
  entries: readonly string[],
  cutoff: number,
) {
  const rows: TimedLap[] = [];
  for (const id of entries) {
    let best: TimedLap | undefined;
    for (const lap of byEntry[id] ?? []) {
      const { lap_time_ms: time, lap_end_time_ms: completedAt } = lap;
      if (
        lap.is_generated ||
        lap.is_deleted ||
        lap.pit_in_time_ms != null ||
        lap.pit_out_time_ms != null ||
        completedAt == null ||
        completedAt > cutoff ||
        time == null ||
        time < 10000
      )
        continue;
      const timed = { id, lap, time, completedAt };
      if (!best || compareLap(timed, best) < 0) best = timed;
    }
    if (best) rows.push(best);
  }
  return rows.sort(compareLap);
}
