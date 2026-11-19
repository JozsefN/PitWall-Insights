import assert from "node:assert/strict";
import test from "node:test";
import type { SessionEntryDto } from "../src/data/contracts/sessions.contracts.ts";
import type { TimingTowerDto } from "../src/data/contracts/session-timing.contracts.ts";
import {
  timingHeader,
  timingRows,
} from "../src/features/sessions/timing-tower-model.ts";

const roster = [
  {
    id: "a",
    car_number: "4",
    grid_position: 1,
    result_position: 2,
    laps_completed: 2,
  },
  {
    id: "b",
    car_number: "16",
    grid_position: 2,
    result_position: 1,
    laps_completed: 2,
  },
  {
    id: "c",
    car_number: "63",
    grid_position: 3,
    result_position: 3,
    laps_completed: 1,
  },
  {
    id: "d",
    car_number: "23",
    grid_position: null,
    result_position: 4,
    status: "Retired",
    laps_completed: 0,
  },
] as SessionEntryDto[];

const timeline: TimingTowerDto = {
  kind: "race",
  scheduled_laps: 2,
  race_crossings: [
    [78_000, 1],
    [160_000, 2],
  ],
  flags: [
    [1000, "GREEN", []],
    [40_000, "LOCAL YELLOW", [4]],
    [60_000, "SAFETY CAR", []],
    [160_000, "CHEQUERED", []],
  ],
  ranks: { 4: [[32_000, 2]], 16: [[30_000, 1]] },
  gaps: {
    4: [[38_000, 2400, 2400]],
    63: [
      [38_000, 6400, 4000],
      [150_000, -1, -1],
    ],
  },
  race_laps: {
    4: [
      [79_000, 1, 2],
      [162_000, 2, 2],
    ],
    16: [
      [78_000, 1, 1],
      [160_000, 2, 1],
    ],
    63: [[84_000, 1, 3]],
  },
  timed_laps: {},
  best_laps: {},
  classified_gaps: { 4: 4100, 16: 0, 63: -1 },
};

test("running order starts on the grid, resolves a passing update and restores the grid when rewound", () => {
  const initial = timingRows(timeline, roster, 0, "simulation");
  assert.deepEqual(
    initial.map((row) => row.position),
    [1, 2, 3, null],
  );
  assert.equal(initial[1].gap, null);
  assert.equal(initial[3].status, undefined);
  const pass = timingRows(timeline, roster, 31_000, "simulation");
  assert.equal(pass[0].entry.id, "b");
  assert.equal(pass.filter((row) => row.position === 1).length, 1);
  assert.equal(
    timingRows(timeline, roster, 39_000, "simulation")[2].interval,
    4000,
  );
  assert.deepEqual(timingRows(timeline, roster, 0, "simulation"), initial);
  assert.ok(
    timingRows(
      { ...timeline, ranks: {}, race_laps: {} },
      roster,
      90_000,
      "simulation",
    ).every((row) => row.position == null),
  );
});

test("reported gaps keep lap-down units, expire, and fall back to a shared crossing", () => {
  const observed = timingRows(timeline, roster, 39_000, "simulation")[2];
  assert.deepEqual(
    [observed.gap, observed.interval, observed.source],
    [6400, 4000, "reported"],
  );
  const crossed = timingRows(timeline, roster, 89_000, "simulation")[2];
  assert.deepEqual(
    [crossed.gap, crossed.interval, crossed.source],
    [6000, 5000, "line"],
  );
  assert.equal(timingRows(timeline, roster, 152_000, "simulation")[2].gap, -1);
  assert.equal(
    timingRows(timeline, roster, 270_000, "simulation")[2].gap,
    null,
  );
});

test("race laps and individual cautions follow the replay position", () => {
  assert.deepEqual(timingHeader(timeline, 40_500, "simulation"), {
    flag: "LOCAL YELLOW",
    sectors: [4],
    lap: 1,
    total: 2,
  });
  assert.deepEqual(timingHeader(timeline, 81_000, "simulation"), {
    flag: "SAFETY CAR",
    sectors: [],
    lap: 2,
    total: 2,
  });
  assert.equal(timingHeader(timeline, 162_000, "simulation").flag, "CHEQUERED");
  assert.equal(timingHeader(timeline, 220, "simulation").flag, undefined);
});

test("lookback uses classified gaps and DNF while preserving all drivers", () => {
  const result = timingRows(timeline, roster, 0, "lookback");
  assert.equal(result.length, roster.length);
  assert.equal(result[1].gap, 4100);
  assert.equal(result[2].interval, -1);
  assert.equal(result[3].status, "DNF");
  const archive = timingRows(
    { ...timeline, classified_gaps: {} },
    roster,
    0,
    "lookback",
  );
  assert.equal(archive[1].gap, 2000);
});

test("timed sessions expose completed best laps and apply deletion or reinstatement when reported", () => {
  const timed: TimingTowerDto = {
    ...timeline,
    kind: "timed",
    timed_laps: {
      4: [
        [80_000, 74_000, []],
        [
          160_000,
          70_000,
          [
            [169_000, false],
            [178_000, true],
          ],
        ],
      ],
      16: [[87_000, 72_000, []]],
    },
    best_laps: { 4: 70_000, 16: 72_000 },
  };
  assert.ok(
    timingRows(timed, roster, 79_999, "simulation").every(
      (row) => row.position == null,
    ),
  );
  assert.equal(
    timingRows(timed, roster, 160_000, "simulation")[0].time,
    70_000,
  );
  assert.equal(
    timingRows(timed, roster, 170_000, "simulation")[0].time,
    72_000,
  );
  assert.equal(
    timingRows(timed, roster, 178_000, "simulation")[0].time,
    70_000,
  );
  assert.equal(timingRows(timed, roster, 0, "lookback")[0].entry.id, "b");
});
