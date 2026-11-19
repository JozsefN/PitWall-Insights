import assert from "node:assert/strict";
import { test } from "node:test";
import type {
  CarTelemetrySampleDto,
  EntryLapDto,
} from "../src/data/contracts/sessions.contracts.ts";
import { replayCardData } from "../src/widgets/driver-cards/replay-card-data.ts";
import {
  lapPositions,
  tyreRuns,
} from "../src/widgets/race-timing/timing-data.ts";
import { supportedSessionKinds } from "../src/features/dashboards/compatibility.ts";
import { rankedTimedLaps } from "../src/widgets/race-timing/replay-timed-laps.ts";

test("the driver card clears stale values and breaks the trace over sample gaps", () => {
  const samples = [1000, 1500, 4100, 4500, 5200].map(
    (session_time_ms, index) =>
      ({ session_time_ms, speed_kph: index * 80 }) as CarTelemetrySampleDto,
  );
  assert.equal(replayCardData(samples, 999).hasPriorSample, false);
  const visible = replayCardData(samples, 4500);
  assert.equal(visible.sample?.speed_kph, 240);
  assert.equal(visible.speedPath.match(/M/g)?.length, 2);
  assert.ok(visible.hasSpeedTrace);
  assert.equal(replayCardData(samples, 8000).sample, undefined);
  assert.equal(replayCardData(samples, 1300).hasSpeedTrace, false);
});

test("tyre sets and running ranks are revealed only after their lap completes", () => {
  const lap = (
    lap_number: number,
    compound: string,
    stint_number: number,
    lap_position: number,
  ) =>
    ({
      lap_number,
      compound,
      stint_number,
      lap_position,
      tyre_life: lap_number,
      lap_start_time_ms: (lap_number - 1) * 80000,
      lap_end_time_ms: lap_number * 80000,
    }) as EntryLapDto;
  const laps = [
    lap(4, "MEDIUM", 2, 3),
    lap(1, "SOFT", 1, 5),
    lap(2, "SOFT", 1, 4),
    { ...lap(3, "HARD", 2, 2), is_generated: true },
    lap(5, "MEDIUM", 3, 1),
  ];
  assert.deepEqual(lapPositions(laps, 310000), [
    { lap: 1, position: 5 },
    { lap: 2, position: 4 },
  ]);
  assert.deepEqual(
    tyreRuns(laps, 310000).map((run) => [run.from, run.to, run.compound]),
    [[1, 2, "SOFT"]],
  );
  assert.deepEqual(
    tyreRuns(laps).map((run) => [run.from, run.to, run.compound]),
    [
      [1, 2, "SOFT"],
      [4, 4, "MEDIUM"],
      [5, 5, "MEDIUM"],
    ],
  );
  assert.deepEqual(tyreRuns(laps, 79000), []);
});

test("running order is restricted to race and sprint, while tyre history includes qualifying", () => {
  assert.deepEqual(supportedSessionKinds(["position-history"]), [
    "race",
    "sprint",
  ]);
  assert.ok(supportedSessionKinds(["tyre-timeline"]).includes("qualifying"));
});

test("the automatic strategy panels are Grand Prix only", () => {
  for (const panel of [
    "strategy-call",
    "intervention-risk",
    "tyre-outlook",
    "rival-comparison",
    "rival-pit-scenarios",
  ] as const) {
    assert.deepEqual(supportedSessionKinds([panel]), ["race"]);
  }
});

test("replay timing board ranks only completed valid laps and rewinds the sector reference", () => {
  const lap = (
    lap_number: number,
    lap_end_time_ms: number,
    lap_time_ms: number,
  ) =>
    ({
      lap_number,
      lap_end_time_ms,
      lap_time_ms,
      sector_1_time_ms: lap_time_ms / 3,
    }) as EntryLapDto;
  const rows = {
    one: [lap(1, 82000, 82000), lap(2, 165000, 80000)],
    two: [
      lap(1, 86000, 81000),
      { ...lap(2, 165000, 79000), is_deleted: true },
      { ...lap(3, 260000, 78000), pit_out_time_ms: 170000 },
      { ...lap(4, 360000, 74000), is_generated: true },
    ],
    unselected: [lap(1, 76000, 75000)],
  };
  assert.deepEqual(rankedTimedLaps(rows, ["one", "two"], 81999), []);
  assert.equal(rankedTimedLaps(rows, ["one", "two"], 86000)[0].id, "two");
  assert.equal(
    rankedTimedLaps(
      { one: [lap(1, 89000, 81000)], two: rows.two },
      ["one", "two"],
      89000,
    )[0].id,
    "two",
  );
  assert.deepEqual(
    rankedTimedLaps(rows, ["one", "two"], 360000).map(({ id, lap }) => [
      id,
      lap.lap_number,
      lap.sector_1_time_ms,
    ]),
    [
      ["one", 2, 80000 / 3],
      ["two", 1, 81000 / 3],
    ],
  );
});
