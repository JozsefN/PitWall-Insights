export type TimingTowerDto = {
  kind: "race" | "timed";
  scheduled_laps: number | null;
  race_crossings: [timeMs: number, lap: number][];
  flags: [timeMs: number, flag: string | null, sectors: number[]][];
  ranks: Record<string, [timeMs: number, position: number][]>;
  gaps: Record<
    string,
    [timeMs: number, leader: number | null, ahead: number | null][]
  >;
  race_laps: Record<
    string,
    [timeMs: number, lap: number, position: number | null][]
  >;
  timed_laps: Record<
    string,
    [
      timeMs: number,
      lapTimeMs: number,
      decisions: [timeMs: number, allowed: boolean][],
    ][]
  >;
  best_laps: Record<string, number>;
  classified_gaps: Record<string, number | null>;
};
