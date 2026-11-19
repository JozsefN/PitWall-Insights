import { test } from "node:test";
import assert from "node:assert/strict";
import { tokenExpiresSoon } from "../src/features/auth/session-token.ts";
import { buildLinePath } from "../src/features/sessions/session-utils.ts";
import { retainSnapshot } from "../src/features/sessions/snapshot-refresh.ts";
import { mapOverlayColour } from "../src/widgets/track-map/utils/circuit-overlays.ts";
import { findPointAtTime } from "../src/widgets/track-map/utils/geometry.ts";
import type { TrackMapPoint } from "../src/widgets/track-map/models.ts";
import { radioClipsInWindow } from "../src/widgets/review/radio-clips.ts";
import {
  buildReplayClock,
  formatReplayElapsed,
  sampledSessionTelemetry,
} from "../src/features/sessions/replay-timeline.ts";

test("replay display starts at zero while retaining the source timestamps", () => {
  const start = 7_415_000;
  assert.equal(formatReplayElapsed(start, start), "0:00");
  assert.equal(formatReplayElapsed(start - 1000, start), "0:00");
  assert.equal(formatReplayElapsed(start + 65_000, start), "1:05");
  assert.equal(formatReplayElapsed(start + 3_665_000, start), "1:01:05");
});

test("radio appears after the replay start and its publish time, and disappears on rewind", () => {
  const clip = { entry_id: "a", recording_url: "https://livetiming.formula1.com/audio.mp3", time_ms: 8200, known_at_ms: 9200 };
  const preRace = { ...clip, time_ms: 2000, known_at_ms: 3000 };
  const clips = [clip, preRace];
  const startMs = 8000;
  assert.deepEqual(radioClipsInWindow(clips, { startMs, timeMs: 8900 }), []);
  assert.deepEqual(radioClipsInWindow(clips, { startMs, timeMs: 9200 }), [clip]);
  assert.deepEqual(radioClipsInWindow(clips, { startMs, timeMs: 8000 }), []);
  assert.deepEqual(radioClipsInWindow(clips), clips);
});

test("the archive reveals a clip at its scheduled playhead time and retains the full list", () => {
  const startMs = 5_000;
  const clips = Array.from({ length: 50 }, (_, index) => ({
    entry_id: "a",
    time_ms: startMs + (50 - index) * 1000,
    recording_url: `https://livetiming.formula1.com/${index}.mp3`,
  }));
  assert.deepEqual(radioClipsInWindow(clips, { startMs, timeMs: 5999 }), []);
  assert.deepEqual(radioClipsInWindow(clips, { startMs, timeMs: 6000 }), [clips[49]]);
  assert.deepEqual(radioClipsInWindow(clips, { startMs, timeMs: 55000 }), clips);
});

test("map markers only use fixes at or before the replay clock", () => {
  const first = { sessionTimeMs: 1000, x: 10, y: 20 } as TrackMapPoint;
  const second = { ...first, sessionTimeMs: 2000, x: 60 };
  assert.equal(findPointAtTime([first, second], 999), null);
  assert.equal(findPointAtTime([first, second], 1999), first);
  assert.equal(findPointAtTime([first, second], 2000), second);
});

test("concurrent telemetry traces share elapsed time and measured value scales", () => {
  const domain = { minX: 0, maxX: 20, minY: 0, maxY: 100 };
  const shorter = [{ x: 0, y: 0 }, { x: 10, y: 50 }];
  const longer = [...shorter, { x: 20, y: 100 }];
  const shortPath = buildLinePath(shorter, 200, 100, domain);
  assert.equal(shortPath, "M 12.00 84.00 L 100.00 48.00");
  assert.equal(buildLinePath(longer, 200, 100, domain), `${shortPath} L 188.00 12.00`);
});

test("a sector flag never colours the whole circuit", () => {
  const sector = {
    track_flag: null,
    sectors: [{ number: 7, flag: "YELLOW" }],
    unlocated_caution: false,
  };
  assert.equal(mapOverlayColour({ layer: "flags", flags: sector }), undefined);
  assert.ok(
    mapOverlayColour({
      layer: "flags",
      flags: { ...sector, track_flag: "SAFETY CAR" },
    }),
  );
});

test("refresh retains compatible snapshots without showing future replay data", () => {
  const snapshot = { session_id: "bahrain", as_of_ms: 30000 };
  assert.equal(retainSnapshot(snapshot, true, "bahrain", 35000), snapshot);
  assert.equal(retainSnapshot(snapshot, true, "bahrain", 30000), snapshot);
  assert.equal(retainSnapshot(snapshot, true, "bahrain"), snapshot);
  assert.equal(retainSnapshot(snapshot, true, "bahrain", 25000), undefined);
  assert.equal(retainSnapshot(snapshot, false, "bahrain", 35000), undefined);
  assert.equal(retainSnapshot(snapshot, true, "australia", 35000), undefined);
});

test("replay clock includes the whole session and its exact final time within a bounded size", () => {
  for (const duration of [0, 1543, 7200123, 24 * 3600_000]) {
    const ticks = buildReplayClock(3000000, 3000000 + duration);
    assert.equal(ticks[0].session_time_ms, 3000000);
    assert.equal(ticks.at(-1)!.session_time_ms, 3000000 + duration);
    assert.ok(ticks.length <= 20002);
    assert.ok(
      ticks.every(
        (tick, index) =>
          index === 0 ||
          tick.session_time_ms > ticks[index - 1].session_time_ms,
      ),
    );
  }
  assert.deepEqual(buildReplayClock(5, 1), []);
  assert.deepEqual(buildReplayClock(NaN, 1), []);
});

test("session-wide replay and lookback sampling covers the full time range within the API budget", () => {
  for (const duration of [90 * 60_000, 3 * 3600_000, 6 * 3600_000]) {
    const start = 500000;
    const end = start + duration;
    const window = sampledSessionTelemetry(start, end);
    assert.equal(window.sessionTimeFromMs, start);
    assert.equal(window.sessionTimeToMs, end);
    assert.ok(window.sampleIntervalMs >= 500);
    assert.ok(Math.ceil(duration / window.sampleIntervalMs) + 1 < window.limit);
  }
});

test("active authentication renews before expiry and handles malformed tokens", () => {
  const now = Date.now();
  const token = (expires: number) =>
    `header.${btoa(JSON.stringify({ exp: expires }))}.signature`;
  assert.equal(tokenExpiresSoon(token((now + 240000) / 1000), now), true);
  assert.equal(tokenExpiresSoon(token((now + 3600000) / 1000), now), false);
  assert.equal(tokenExpiresSoon(token((now - 1000) / 1000), now), true);
  assert.equal(tokenExpiresSoon("invalid", now), false);
});
