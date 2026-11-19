import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import catalog from "../../shared/circuit-catalog.json" with { type: "json" };
import type {
  EntryLapDto,
  PositionSampleDto,
  SessionEntryDto,
} from "../src/data/contracts/sessions.contracts.ts";
import { createReplayClock } from "../src/features/sessions/replay-clock.ts";
import {
  resolveTrackMapLayer,
  trackMapLayers,
} from "../src/widgets/track-map/models.ts";
import {
  buildPointsForLap,
  buildTrackPath,
} from "../src/widgets/track-map/utils/geometry.ts";
import {
  buildLookbackTrackMapData,
  pickCircuitReferenceLap,
  prepareReplayTrackMapData,
  type TrackMapEntryInput,
} from "../src/widgets/track-map/utils/track-map-data.ts";
import { illustrateTrackEdges } from "../src/widgets/track-map/utils/track-envelope.ts";
import {
  boundedCurve,
  curvePoint,
  smoothTrackPath,
} from "../src/widgets/track-map/utils/track-curves.ts";
import {
  illustratedRoadWidthLimitM,
  mapScaleBar,
  metresToMapUnits,
  replayCarDimensions,
} from "../src/widgets/track-map/utils/track-scale.ts";
import {
  buildMappedRoad,
  roadMatchesLap,
} from "../src/widgets/track-map/utils/mapped-road.ts";
import {
  circuitRoadAssets,
  sessionCircuit,
} from "../src/features/circuits/circuit-catalog.ts";
import { parseRoadCsv } from "../src/data/circuit-road-csv.ts";
import { registerCircuitRoad } from "../src/widgets/track-map/utils/circuit-registration.ts";

function sample(
  x: number,
  y: number,
  time: number,
  lapId = "lap",
): PositionSampleDto {
  return {
    x,
    y,
    z: 0,
    id: String(time),
    tick_id: null,
    lap_id: lapId,
    stint_id: null,
    sample_seq: time,
    session_time_ms: time,
    source_time_utc: null,
    source: "test",
    track_status: "1",
  };
}

test("old pit-layer layouts open the track and the layer selector has no pit toggle", () => {
  assert.equal(resolveTrackMapLayer("pits"), "track");
  assert.equal(resolveTrackMapLayer("flags"), "flags");
  assert.equal(resolveTrackMapLayer("constructor"), "track");
  assert.equal(Object.hasOwn(trackMapLayers, "pits"), false);
});

function lap(id: string, number: number, start: number, duration: number) {
  return {
    id,
    lap_number: number,
    lap_start_time_ms: start,
    lap_end_time_ms: start + duration,
    lap_time_ms: duration,
    pit_in_time_ms: null,
    pit_out_time_ms: null,
    track_status: "1",
  } as EntryLapDto;
}

function input(
  samples: PositionSampleDto[],
  laps: EntryLapDto[] = [],
): TrackMapEntryInput {
  return {
    entry: {
      id: "a",
      driver_name: "Driver A",
      car_number: "1",
    } as SessionEntryDto,
    label: "Driver A",
    color: "gold",
    samples,
    laps,
  };
}

function loop(
  centerX: number,
  centerY: number,
  radius: number,
  time = 0,
  id = "lap",
) {
  return Array.from({ length: 81 }, (_, index) => {
    const radians = (index / 80) * Math.PI * 2;
    return sample(
      centerX + radius * Math.cos(radians),
      centerY + radius * Math.sin(radians),
      time + index * 450,
      id,
    );
  });
}

test("map uses a closed racing lap and does not mistake a dense partial trace for the circuit", () => {
  const full = loop(11000, 18000, 4500);
  const partial = Array.from({ length: 190 }, (_, i) =>
    sample(10000 + i * 85, 18000 + i * 32, 40000 + i * 200, "partial"),
  );
  const prepared = prepareReplayTrackMapData([
    input(
      [...full, ...partial],
      [lap("lap", 1, 0, 36000), lap("partial", 2, 40000, 37800)],
    ),
  ]);
  const first = prepared(2000);
  const after = prepared(55000);
  assert.ok(buildTrackPath(first.outlinePoints).endsWith("Z"));
  assert.ok(first.outlinePoints.every((point) => point.lapNumber === 1));
  assert.strictEqual(first.outlinePoints, after.outlinePoints);
  assert.strictEqual(first.illustratedEdges, after.illustratedEdges);
});

test("a crossing at the centre does not disqualify an otherwise complete lap", () => {
  const points = Array.from({ length: 121 }, (_, index) => {
    const angle = (2 * Math.PI * index) / 120;
    return sample(
      10000 + 4500 * Math.sin(angle),
      4000 + 2700 * Math.sin(2 * angle),
      index * 500,
    );
  });
  const data = buildLookbackTrackMapData(
    [input(points, [lap("lap", 1, 0, 60000)])],
    1,
  );
  assert.equal(data.outlinePoints.length, points.length);
});

test("a partial lap uses a single clean timed reference even when later drivers supply it", () => {
  const selected = lap("selected", 1, 0, 60000);
  const pitLap = { ...lap("pit", 2, 60000, 40000), pit_in_time_ms: 97500 };
  const clean = { ...lap("clean", 3, 100000, 62000), is_accurate: true };
  const flags = {
    ...lap("yellow", 4, 162000, 50000),
    is_accurate: true,
    track_status: "2",
  };
  const earlier = input([], [selected, pitLap, flags]);
  const later = input([], [clean]);
  const chosen = pickCircuitReferenceLap(
    [...Array(12).fill(earlier), later],
    1,
  );
  assert.equal(chosen?.input, later);
  assert.equal(chosen?.lap, clean);
  assert.equal(
    pickCircuitReferenceLap([input([], [selected, pitLap])], 1),
    undefined,
  );
});

test("interpolation uses only observed fixes, breaks on a teleport and expires stale cars", () => {
  const frame = prepareReplayTrackMapData([
    input([
      sample(100, 300, 1000),
      sample(200, 300, 1500),
      sample(300, 300, 2000),
      sample(9800, 1300, 2500),
    ]),
  ]);
  assert.equal(frame(800, true).traces.length, 0);
  assert.equal(frame(2325, true).traces[0]?.currentPoint?.x, 125);
  assert.equal(frame(1875).traces[0]?.currentPoint?.x, 200);
  const jump = frame(2500).traces[0];
  assert.equal(jump.currentPoint?.x, 9800);
  assert.equal(jump.points.length, 1);
  assert.equal(frame(3699, true).traces[0]?.currentPoint?.x, 300);
  assert.equal(frame(3700, true).traces[0]?.points.length, 1);
  assert.equal(frame(7501, true).traces.length, 0);
});

test("illustrated edges remain bounded and can be drawn without repeated laps", () => {
  const center = buildPointsForLap(loop(11000, 18000, 4500), 1);
  const wide = buildPointsForLap(loop(11000, 18000, 4570), 1);
  const empty = illustrateTrackEdges(center, []);
  const shaped = illustrateTrackEdges(
    center,
    [wide, wide, wide],
    illustratedRoadWidthLimitM(
      sessionCircuit({ event_name: "Emilia Romagna" }),
    ),
  );
  assert.ok(empty && shaped);
  assert.equal(shaped.left.length, shaped.right.length);
  assert.ok(buildTrackPath(shaped.right).endsWith("Z"));
  assert.notDeepEqual(shaped.left, empty.left);
  assert.ok(
    shaped.left.every(
      (point, index) =>
        Math.hypot(
          point.x - shaped.right[index].x,
          point.y - shaped.right[index].y,
        ) <= 150.001,
    ),
  );
  assert.ok(illustrateTrackEdges(center.slice(0, 3), []));
});

test("mapped road registration preserves unequal widths and rejects a displaced lap", () => {
  const csv = Array.from({ length: 81 }, (_, index) => {
    const angle = (index / 80) * 2 * Math.PI;
    return [450 * Math.cos(angle), 450 * Math.sin(angle), 6, 4].join(",");
  }).join("\n");
  const rows = parseRoadCsv(csv);
  assert.ok(rows);
  const road = buildMappedRoad(rows, {
    angle: Math.PI / 2,
    east: 10,
    north: 20,
  });
  assert.equal(road.centre.length, 80);
  assert.ok(
    Math.abs(
      Math.hypot(
        road.edges.left[0].x - road.edges.right[0].x,
        road.edges.left[0].y - road.edges.right[0].y,
      ) - 100,
    ) < 1e-8,
  );
  assert.ok(roadMatchesLap(road, road.edges.left));
  assert.equal(
    roadMatchesLap(
      road,
      road.edges.left.map((point) => ({ ...point, x: point.x + 720 })),
    ),
    false,
  );
});

test("qualifying lap lookback preserves the original lateral points around an apex", () => {
  const samples = Array.from({ length: 11 }, (_, index) =>
    sample(index * 60, index === 5 ? 260 : 310, index * 250),
  );
  const result = buildLookbackTrackMapData(
    [input(samples, [lap("lap", 1, 0, 2500)])],
    1,
  );
  assert.deepEqual(
    result.traces[0].points.map(({ x, y }) => [x, y]),
    samples.map(({ x, y }) => [x, y]),
  );
});

test("the replay retains the previous lap trail across frames", () => {
  const current = loop(10000, 5000, 4500, 36100, "second");
  const first = loop(10000, 5000, 4500, 0, "first");
  const frame = prepareReplayTrackMapData([
    input(
      [...first, ...current],
      [lap("first", 1, 0, 36100), lap("second", 2, 36100, 36000)],
    ),
  ]);
  assert.equal(frame(37000).traces[0].lapNumber, 2);
  assert.ok(frame(37000).traces[0].previousLapPoints.length > 30);
  assert.strictEqual(
    frame(37000).traces[0].previousLapPoints,
    frame(38000).traces[0].previousLapPoints,
  );
});

test("all bundled circuit centrelines register in a shifted session frame without rescaling", () => {
  for (const circuit of catalog.circuits) {
    const { centreline } = circuitRoadAssets(circuit);
    const { id } = circuit;
    assert.equal(centreline.width, "estimated");
    assert.ok(centreline.credits.length, id);
    const rows = parseRoadCsv(
      readFileSync(
        new URL(`../public/circuit-roads/${centreline.file}`, import.meta.url),
        "utf8",
      ),
    );
    assert.ok(rows, id);
    const width =
      "estimatedWidthM" in circuit
        ? circuit.estimatedWidthM
        : catalog.defaultEstimatedWidthM;
    assert.ok(
      rows.every(([, , right, left]) => right + left === width),
      id,
    );
    const outline = rows.map(([x, y]) => ({
      x: (-y + 290) * 10,
      y: (x - 70) * 10,
    }));
    const road = registerCircuitRoad(rows, outline);
    assert.ok(road && roadMatchesLap(road, outline), id);
    assert.equal(
      registerCircuitRoad(
        rows,
        outline.map(({ x, y }) => ({ x: x * 1.4, y })),
      ),
      undefined,
      `${id} should reject the wrong scale`,
    );
  }
});

test("every width profile registers through the same path and retains varying widths", () => {
  for (const circuit of catalog.circuits) {
    const { profile } = circuitRoadAssets(circuit);
    if (!profile) continue;
    assert.equal(profile.width, "profile");
    assert.ok(profile.credits.length, circuit.id);
    const rows = parseRoadCsv(
      readFileSync(
        new URL(`../public/circuit-roads/${profile.file}`, import.meta.url),
        "utf8",
      ),
    );
    assert.ok(rows, circuit.id);
    const outline = rows.map(([x, y]) => ({
      x: (y + 290) * 10,
      y: (-x - 70) * 10,
    }));
    const road = registerCircuitRoad(rows, outline);
    assert.ok(road && roadMatchesLap(road, outline), circuit.id);
    const widths = road.edges.left.map((point, i) =>
      Math.hypot(
        point.x - road.edges.right[i].x,
        point.y - road.edges.right[i].y,
      ),
    );
    assert.ok(Math.max(...widths) - Math.min(...widths) > 5, circuit.id);
  }
});

test("the common CSV parser rejects malformed rows and incomplete roads", () => {
  assert.equal(parseRoadCsv("0,0,6,6"), undefined);
  for (const row of ["1,,6,6", "NaN,0,6,6", "1,0,-1,6", "1,0,6,6,5"]) {
    assert.equal(parseRoadCsv(`${"0,0,6,6\n".repeat(31)}${row}\n`), undefined);
  }
});

test("circuit curves preserve every join and stay within the allowed rounding distance", () => {
  const corners = [
    { x: 0, y: 0 },
    { x: 100, y: 0 },
    { x: 100, y: 100 },
    { x: 0, y: 100 },
  ];
  const path = smoothTrackPath(corners, true, 12);
  assert.equal(path.match(/ C /g)?.length, 4);
  assert.match(path, /100\.00 0\.00 C /);
  assert.ok(path.endsWith("0.00 0.00 Z"));
  const curve = boundedCurve(
    corners[0],
    corners[1],
    { x: 0, y: -1 },
    { x: 0, y: 1 },
    12,
  );
  assert.deepEqual(curvePoint(curve, 0), corners[0]);
  assert.deepEqual(curvePoint(curve, 1), corners[1]);
  for (let step = 0; step <= 20; step++)
    assert.ok(Math.abs(curvePoint(curve, step / 20).y) <= 12);
});

test("driver headings stay continuous across a turn without seeing future fixes", () => {
  const samples = [
    sample(100, 300, 1000),
    sample(200, 300, 1500),
    sample(270, 365, 2000),
    sample(282, 455, 2500),
  ];
  const trajectory = prepareReplayTrackMapData([input(samples)]);
  const before = trajectory(3199, true).traces[0];
  const after = trajectory(3201, true).traces[0];
  assert.ok(Math.abs(before.headingDeg - after.headingDeg) < 2);
  assert.ok(
    Math.hypot(
      before.currentPoint!.x - after.currentPoint!.x,
      before.currentPoint!.y - after.currentPoint!.y,
    ) < 1,
  );
  const withFuture = prepareReplayTrackMapData([
    input([...samples, sample(315, 540, 3350)]),
  ]);
  assert.deepEqual(
    trajectory(3201, true).traces[0].currentPoint,
    withFuture(3201, true).traces[0].currentPoint,
  );
});

test("a late update resumes from the held position without jumping at arrival", () => {
  const frame = prepareReplayTrackMapData([
    input([
      sample(500, 200, 800),
      sample(650, 200, 1300),
      sample(1160, 200, 3000),
      sample(1310, 200, 3500),
    ]),
  ]);
  const x = (time: number) => frame(time, true).traces[0]!.currentPoint!.x;
  assert.equal(x(2999), x(3000));
  assert.ok(x(3001) - x(3000) < 1);
  assert.ok(x(3500) > x(3000) && x(3500) < 1160);
  assert.equal(x(4200), 1160);
});

test("noise correction reduces small oscillations and preserves a sustained lateral move", () => {
  const frame = prepareReplayTrackMapData([
    input([
      sample(100, 400, 1000),
      sample(300, 412, 1500),
      sample(500, 400, 2000),
      sample(700, 437, 2500),
      sample(900, 445, 3000),
      sample(1100, 445, 3500),
      sample(1300, 445, 4000),
    ]),
  ]);
  const point = (time: number) => frame(time, true).traces[0]!.currentPoint!;
  const corrected = point(2700);
  assert.equal(corrected.x, 300);
  assert.ok(corrected.y < 405);
  assert.ok(Math.abs(point(3700).y - 437) <= 9);
  assert.equal(point(4700).y, 445);
  assert.deepEqual(point(2700), corrected);
});

test("car dimensions and the scale bar share map metres", () => {
  const { lengthM, widthM } = replayCarDimensions(2025);
  assert.deepEqual(
    [metresToMapUnits(lengthM), metresToMapUnits(widthM)],
    [55, 20],
  );
  assert.equal(replayCarDimensions(2026).widthM, 1.9);
  for (const density of [1, 2.5, 10]) {
    const scale = mapScaleBar(density)!;
    assert.equal((scale.widthPx * density) / metresToMapUnits(1), scale.metres);
  }
});

test("map frames do not publish counter and analysis updates", () => {
  const clock = createReplayClock();
  const observed: (number | null)[] = [];
  const unsubscribe = clock.frame.subscribe(() =>
    observed.push(clock.frame.getTime()),
  );
  clock.frame.setTime(100);
  clock.frame.setTime(125);
  clock.frame.setTime(125);
  assert.deepEqual(observed, [100, 125]);
  assert.equal(clock.readout.getTime(), null);
  assert.equal(clock.review.getTime(), null);
  unsubscribe();
  clock.frame.setTime(150);
  assert.deepEqual(observed, [100, 125]);
});
