import type { EntryLapDto } from "../../data/contracts/sessions.contracts";

export type TyreRun = {
  from: number;
  to: number;
  stint: number | null;
  compound: string | null;
  lastCompletedAge: number | null;
};

function recordedLaps(laps: readonly EntryLapDto[]) {
  return laps
    .filter((lap) => !lap.is_generated && lap.lap_number > 0)
    .sort((a, b) => a.lap_number - b.lap_number);
}

export function tyreRuns(laps: readonly EntryLapDto[], cutoffMs?: number) {
  const runs: TyreRun[] = [];
  for (const lap of recordedLaps(laps)) {
    if (
      cutoffMs != null &&
      (lap.lap_end_time_ms == null || lap.lap_end_time_ms > cutoffMs)
    )
      continue;
    const age = lap.tyre_life;
    const previous = runs.at(-1);
    if (
      previous &&
      previous.to + 1 === lap.lap_number &&
      previous.stint === lap.stint_number &&
      previous.compound === lap.compound
    ) {
      previous.to = lap.lap_number;
      previous.lastCompletedAge = age ?? previous.lastCompletedAge;
    } else {
      runs.push({
        from: lap.lap_number,
        to: lap.lap_number,
        stint: lap.stint_number,
        compound: lap.compound,
        lastCompletedAge: age,
      });
    }
  }
  return runs;
}

export function lapPositions(laps: readonly EntryLapDto[], cutoffMs?: number) {
  return recordedLaps(laps).flatMap((lap) => {
    const position = lap.lap_position;
    const end = lap.lap_end_time_ms;
    if (
      position == null ||
      !Number.isInteger(position) ||
      position < 1 ||
      end == null ||
      (cutoffMs != null && end > cutoffMs)
    )
      return [];
    return [{ lap: lap.lap_number, position }];
  });
}

export function lapAxis(lastLap: number) {
  const target = Math.max(1, Math.ceil(lastLap / 6));
  const step = [1, 2, 5, 10, 15, 20].find((tick) => tick >= target) ?? target;
  const end = Math.max(5, lastLap);
  const ticks = Array.from(
    { length: Math.floor(end / step) },
    (_, index) => (index + 1) * step,
  );
  return { end, step, ticks };
}
