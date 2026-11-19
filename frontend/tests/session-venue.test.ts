import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";
import catalog from "../../shared/circuit-catalog.json" with { type: "json" };
import {
  sessionCircuit,
  sessionHostFlag,
} from "../src/features/circuits/circuit-catalog.ts";

test("older sessions resolve by venue, then by event name, with a country fallback", () => {
  assert.equal(
    sessionHostFlag({ location: "Suzuka", event_name: "Qualifying" }),
    "jp",
  );
  assert.equal(sessionHostFlag({ event_name: "British Grand Prix" }), "gb");
  assert.equal(
    sessionHostFlag({ country: " United Kingdom ", event_name: "Qualifying" }),
    "gb",
  );
  assert.equal(
    sessionHostFlag({ country: "JP", event_name: "Qualifying" }),
    "jp",
  );
  assert.equal(
    sessionHostFlag({ location: "Sao Paulo", event_name: "Qualifying" }),
    "br",
  );
  assert.equal(
    sessionHostFlag({ event_name: "Emilia Romagna Grand Prix" }),
    "it",
  );
  assert.equal(sessionHostFlag({ event_name: "Miami Grand Prix" }), "us");
  assert.equal(sessionHostFlag({ event_name: "Las Vegas Grand Prix" }), "us");
  assert.equal(
    sessionHostFlag({ country: "constructor", event_name: "Unknown event" }),
    undefined,
  );
  assert.equal(
    sessionCircuit({ location: "Madrid", event_name: "Spanish Grand Prix" })
      ?.id,
    "es-2026",
  );
});

test("provider circuit identity distinguishes venues even when the event name is reused", () => {
  const event_name = "Bahrain Grand Prix";
  const relocated = {
    circuit_key: "12",
    location: "Kuala Lumpur",
    country: "Bahrain",
    event_name,
  };
  assert.equal(sessionCircuit(relocated)?.id, "my-1999");
  assert.equal(sessionHostFlag(relocated), "my");
  assert.equal(sessionHostFlag({ ...relocated, circuit_key: undefined }), "my");
  assert.equal(
    sessionCircuit({ circuit_key: "63", event_name })?.id,
    "bh-2002",
  );
  assert.equal(sessionHostFlag({ circuit_key: "63", event_name }), "bh");
  assert.equal(sessionCircuit({ circuit_key: "999", event_name }), undefined);
  assert.equal(
    sessionHostFlag({ circuit_key: "999", country: "Malaysia", event_name }),
    "my",
  );
});

test("one catalog covers all venue keys, centreline assets and local flags", () => {
  const centrelines = readdirSync(
    new URL("../public/circuit-roads/centrelines", import.meta.url),
  );
  const ids = catalog.circuits.map((circuit) => circuit.id);
  assert.deepEqual(centrelines.sort(), ids.map((id) => `${id}.csv`).sort());
  assert.equal(
    new Set(catalog.circuits.map((circuit) => circuit.openf1Key)).size,
    ids.length,
  );
  const hosts: Record<string, { name: string; aliases: string[] }> =
    catalog.hosts;
  for (const circuit of catalog.circuits) {
    assert.ok(hosts[circuit.host], circuit.id);
    const venue = { event_name: "", circuit_key: String(circuit.openf1Key) };
    assert.equal(sessionCircuit(venue)?.id, circuit.id);
    assert.equal(sessionHostFlag(venue), circuit.host);
    for (const alias of circuit.aliases) {
      assert.equal(
        sessionCircuit({ event_name: alias })?.id,
        circuit.id,
        alias,
      );
    }
  }
  for (const [code, host] of Object.entries(hosts)) {
    assert.equal(sessionHostFlag({ country: host.name, event_name: "" }), code);
    const image = readFileSync(
      new URL(`../public/host-flags/${code}.webp`, import.meta.url),
    );
    assert.equal(image.toString("ascii", 0, 4), "RIFF", code);
    assert.equal(image.toString("ascii", 8, 12), "WEBP", code);
  }
});
