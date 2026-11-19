import type {
  SessionEntryDto,
  SessionPitMapDto,
  SessionPitVisitDto,
} from "../../../data/contracts/sessions.contracts";
import { getEntryAccent } from "../../../features/sessions/session-utils.ts";

export function preparePitMap(
  data: SessionPitMapDto,
  entries: SessionEntryDto[],
) {
  const teams = new Map(
    entries.map((entry, index) => [
      entry.team_id,
      {
        name: entry.team_name ?? "Team",
        color: getEntryAccent(entry, index),
      },
    ]),
  );
  const boxes = data.boxes
    .flatMap(({ team_id, point: [x, y], known_at_ms }) => {
      const team = teams.get(team_id);
      return team
        ? [{ id: team_id, x, y, knownAtMs: known_at_ms, ...team }]
        : [];
    })
    .sort((a, b) => a.knownAtMs - b.knownAtMs);
  const byDriver = new Map<string, SessionPitVisitDto[]>();
  for (const visit of data.visits) {
    const driver = byDriver.get(visit.entry_id);
    if (driver) driver.push(visit);
    else byDriver.set(visit.entry_id, [visit]);
  }
  return {
    lane: data.lane.map(([x, y]) => ({ x, y })),
    source: data.lane_source ?? "pit_reports",
    boxes,
    byDriver,
  };
}

export type PitMap = ReturnType<typeof preparePitMap>;

export function pitPhaseAt(
  visits: SessionPitVisitDto[] | undefined,
  timeMs: number,
) {
  const visit = visits?.find(
    (row) => row.start_ms <= timeMs && timeMs < row.end_ms,
  );
  if (!visit) return undefined;
  return visit.stopped_from_ms != null &&
    visit.stopped_until_ms != null &&
    visit.stopped_from_ms <= timeMs &&
    timeMs <= visit.stopped_until_ms
    ? ("box" as const)
    : ("lane" as const);
}
