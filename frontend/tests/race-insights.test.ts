import { test } from "node:test";
import assert from "node:assert/strict";
import {
  filterEvents,
  raceUpdateSelection,
  notificationCapacity,
  snapshotCutoff,
  formatEstimate,
} from "../src/features/race-insights/presentation.ts";
import type { RaceEvent } from "../src/features/race-insights/contracts.ts";
import type {
  EntryLapDto,
  SessionEntryDto,
} from "../src/data/contracts/sessions.contracts.ts";
import { buildTrackStatusBands } from "../src/widgets/telemetry/utils/track-status.ts";

test("replay flags use observed events and only fall back to completed laps", () => {
  const lap = {
    lap_number: 1,
    lap_start_time_ms: 1000,
    lap_end_time_ms: 101000,
    sector_1_session_time_ms: 31000,
    sector_2_session_time_ms: 66000,
    track_status: "2",
  } as EntryLapDto;
  const source = {
    entries: [{ id: "a" } as SessionEntryDto],
    lapsByEntryId: { a: [lap] },
  };
  assert.deepEqual(
    buildTrackStatusBands({ ...source, currentTimeLimitMs: 100999 }),
    [],
  );
  assert.equal(
    buildTrackStatusBands({ ...source, currentTimeLimitMs: 101000 })[0].label,
    "Yellow",
  );
  const events = [
    {
      id: "yellow",
      session_time_ms: 25000,
      source_time_utc: null,
      status: "2",
      message: null,
    },
    {
      id: "green",
      session_time_ms: 50000,
      source_time_utc: null,
      status: "1",
      message: null,
    },
  ];
  const [band] = buildTrackStatusBands({
    ...source,
    currentTimeLimitMs: 30000,
    events,
  });
  assert.equal(band.endTimeMs, 30000);
  assert.equal(band.startSector, null);
  assert.equal(band.endSector, null);
});

const event = (
  id: string,
  kind: RaceEvent["kind"],
  time_ms = 100000,
  entry_id: string | null = "a",
  classification: RaceEvent["classification"] = "reported",
  severity: RaceEvent["severity"] = "info",
): RaceEvent => ({
  id,
  kind,
  time_ms,
  entry_id,
  classification,
  severity,
  start_ms: time_ms,
  rival_entry_id: null,
  title: id,
  detail: "fixture",
  support: 0.5,
  evidence: {},
  alternatives: [],
});
test("notification categories, empty selection, severity and unconfirmed events are independent", () => {
  const rows = [
    event("pass", "overtake"),
    event("flag", "yellow_flag", 100000, null),
    event(
      "candidate",
      "possible_incident",
      100000,
      "a",
      "candidate",
      "warning",
    ),
  ];
  assert.deepEqual(filterEvents(rows, { eventTypes: [] }, [], 100000), []);
  assert.deepEqual(
    filterEvents(
      rows,
      { includeCandidates: false, eventTypes: ["overtake"] },
      [],
      100000,
    ).map((row) => row.id),
    ["pass"],
  );
  assert.deepEqual(
    filterEvents(rows, { minSeverity: "warning" }, [], 100000).map(
      (row) => row.id,
    ),
    ["candidate"],
  );
});
test("selected-driver notifications retain global control and related rivals", () => {
  const rival = {
    ...event("rival", "overtake", 100000, "b"),
    rival_entry_id: "a",
  };
  const rows = [
    event("other", "overtake", 100000, "b"),
    event("global", "yellow_flag", 100000, null),
    rival,
  ];
  assert.deepEqual(
    filterEvents(rows, { driverScope: "selected" }, ["a"], 100000).map(
      (row) => row.id,
    ),
    ["global", "rival"],
  );
});
test("model filters require paid access and work on reports-only saved layouts", () => {
  const rows = [
    event("pit", "pit_stop"),
    event("yellow", "yellow_flag", 100000, null),
    event("brake", "braking_anomaly", 100000, "a", "candidate"),
    event("incident", "possible_incident", 100000, "b", "candidate"),
  ];
  const saved = { includeCandidates: false, eventTypes: ["pit_stop", "yellow_flag"] };
  const visible = (filter: Parameters<typeof raceUpdateSelection>[1], modelAccess: boolean) => {
    const selection = raceUpdateSelection(saved, filter, modelAccess);
    return filterEvents(rows, selection.options, [], 100000).map((row) => row.id);
  };
  assert.deepEqual(visible("braking", false), ["pit", "yellow"]);
  assert.deepEqual(visible("all", true), ["pit", "yellow"]);
  assert.deepEqual(visible("braking", true), ["brake"]);
  assert.deepEqual(visible("incidents", true), ["incident"]);
  assert.deepEqual(visible("flags", false), ["yellow"]);
  assert.deepEqual(visible("pits", false), ["pit"]);
  assert.equal(raceUpdateSelection({ includeCandidates: true }, "all", false).includeCandidates, false);
  assert.equal(raceUpdateSelection({ includeCandidates: true }, "all", true).includeCandidates, true);
});
test("replay rewind excludes future messages, deduplicates, and limits the trailing window", () => {
  const rows = [
    event("old", "pit_stop", 1000),
    event("current", "pit_stop", 99000),
    event("future", "pit_stop", 101000),
    event("current", "pit_stop", 99000),
  ];
  assert.deepEqual(
    filterEvents(rows, { lookbackMinutes: 1 }, [], 100000).map((row) => row.id),
    ["current"],
  );
  assert.equal(snapshotCutoff(104999), 100000);
  assert.equal(snapshotCutoff(99999), 95000);
  assert.ok(snapshotCutoff(1) <= 1);
});
test("notification capacity adapts and explicit 3/5 choices remain exact", () => {
  assert.equal(notificationCapacity(425, "auto"), 3);
  assert.equal(notificationCapacity(595, "auto"), 5);
  assert.equal(notificationCapacity(900, 3), 3);
  assert.equal(notificationCapacity(200, 5), 5);
  assert.equal(notificationCapacity(10000, "auto"), 12);
});
test("unavailable estimates are never printed as zero or calibrated percentages", () => {
  assert.equal(formatEstimate(), "Unavailable");
  assert.equal(
    formatEstimate({
      value: 42,
      status: "unavailable",
      unit: "%",
      method: "index",
      support: 0,
      lower: null,
      upper: null,
      uncertainty: null,
      reason: null,
    }),
    "Unavailable",
  );
  assert.equal(
    formatEstimate({
      value: 42,
      status: "available",
      unit: "index",
      method: "index",
      support: 0.5,
      lower: null,
      upper: null,
      uncertainty: null,
      reason: null,
    }),
    "42 / 100",
  );
});
