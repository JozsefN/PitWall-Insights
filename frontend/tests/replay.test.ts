import { test } from "node:test";
import assert from "node:assert/strict";
import { tokenExpiresSoon } from "../src/features/auth/session-token.ts";
import {
  buildReplayClock,
  replaySampleInterval,
} from "../src/features/sessions/replay-timeline.ts";

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

test("replay sampling retains full-race coverage under the API's sample limit", () => {
  for (const duration of [90 * 60_000, 3 * 3600_000, 6 * 3600_000]) {
    const interval = replaySampleInterval(500000, 500000 + duration);
    assert.ok(interval >= 500);
    assert.ok(Math.ceil(duration / interval) + 1 < 20000);
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
