import { test } from "node:test";
import assert from "node:assert/strict";
import {
  widgetCatalog,
  widgetSizeError,
  fitWidgetSize,
} from "../src/widgets/registry/widget.catalog.ts";
import type {
  LayoutRecord,
  WidgetId,
} from "../src/widgets/registry/widget.types.ts";
import {
  classifySession,
  layoutCompatibilityReason,
  sessionKinds,
  supportedSessionKinds,
  widgetBlockReason,
} from "../src/features/dashboards/compatibility.ts";
import {
  canPlace,
  clampResize,
  draftCompatibilityError,
  draftError,
  draftFromLayout,
  draftToConfig,
  emptyDraft,
  findSpace,
  newWidget,
  overlaps,
  validPlacement,
} from "../src/features/dashboards/editor-model.ts";

test("session names distinguish sprint qualifying, sprint and Grand Prix", () => {
  assert.equal(
    classifySession({ session_name: "Sprint Shootout" }),
    "qualifying",
  );
  assert.equal(
    classifySession({ session_name: "Sprint Qualifying" }),
    "qualifying",
  );
  assert.equal(
    classifySession({ session_name: "Sprint", session_type: "Race" }),
    "sprint",
  );
  assert.equal(classifySession({ session_name: "Race" }), "race");
  assert.equal(classifySession({ session_name: "Practice 2" }), "practice");
});

test("qualifying results and race tactics have explicit restrictions", () => {
  assert.match(
    widgetBlockReason("wake-exposure", ["session-lookback"], ["race"])!,
    /Replay only/,
  );
  assert.match(
    widgetBlockReason("wake-exposure", ["live-race"], ["sprint"])!,
    /Grand Prix only/,
  );
  assert.equal(
    widgetBlockReason("wake-exposure", ["live-race"], ["race"]),
    undefined,
  );
  assert.match(
    widgetBlockReason("lookback-driver-cards", ["live-race"], ["qualifying"])!,
    /Lookback only/,
  );
  assert.match(
    widgetBlockReason(
      "lookback-driver-cards",
      ["session-lookback"],
      ["practice"],
    )!,
    /Qualifying only/,
  );
  assert.equal(
    widgetBlockReason("lap-segment-review", ["session-lookback"], ["practice"]),
    undefined,
  );
  assert.deepEqual(
    supportedSessionKinds(["lookback-driver-cards", "stint-analysis"]),
    [],
  );
  for (const policy of Object.values(widgetCatalog)) {
    if (!policy.builderEnabled) continue;
    assert.ok(policy.availabilityNote);
    assert.ok(policy.supportedAudiences.length);
    assert.ok(
      policy.sessionKinds?.length &&
        policy.sessionKinds.every((kind) => sessionKinds.includes(kind)),
    );
  }
});

test("legacy saved mode can expand to both modes without changing panel positions or IDs", () => {
  const draft = emptyDraft("session-lookback");
  const panel = newWidget("weather-history", { x: 2, y: 3, w: 6, h: 8 });
  draft.sections[0].widgets.push(panel);
  const config = draftToConfig(draft, "weather");
  const saved: LayoutRecord = {
    config,
    audience: draft.audience,
    id: "user:weather",
    name: "Weather",
    description: null,
    source: "user",
    schemaVersion: 2,
  };
  assert.match(
    layoutCompatibilityReason(saved, "live-race", "race")!,
    /Saved for Lookback only/,
  );
  const edited = draftFromLayout(saved);
  assert.equal(edited.sections[0].widgets[0].instanceId, panel.instanceId);
  edited.enabledAudiences = ["session-lookback", "live-race"];
  assert.equal(draftCompatibilityError(edited), null);
  const updated = draftToConfig(edited, config.id);
  assert.deepEqual(updated.sections, config.sections);
  assert.equal(
    layoutCompatibilityReason(
      { ...saved, config: updated },
      "live-race",
      "race",
    ),
    undefined,
  );
  edited.sections[0].widgets.push(
    newWidget("lap-table", { x: 2, y: 11, w: 6, h: 5 }),
  );
  assert.match(draftCompatibilityError(edited)!, /Lap Table.*Lookback only/);
});

test("placements reject overlap, out of bounds, fractional and non-finite geometry", () => {
  const box = { x: 0, y: 0, w: 6, h: 5 };
  const widget = newWidget("lap-table", box);
  assert.ok(overlaps(box, { ...box, x: 5 }));
  assert.ok(!overlaps(box, { ...box, x: 6 }));
  assert.ok(canPlace([widget], widget.instanceId, { ...box, y: 1 }));
  assert.ok(!canPlace([widget], "other", box));
  for (const bad of [
    { ...box, x: -1 },
    { ...box, x: 7 },
    { ...box, h: 21 },
    { ...box, y: 198 },
    { ...box, x: 0.5 },
    { ...box, w: Infinity },
  ])
    assert.ok(!validPlacement(bad));
});

test("new widgets find open positions, honor drop intent, and report full grids", () => {
  const widget = newWidget("lap-table", { x: 0, y: 0, w: 6, h: 5 });
  assert.deepEqual(findSpace([widget]), { x: 6, y: 0, w: 6, h: 5 });
  assert.deepEqual(findSpace([widget], { x: 3, y: 6 }), {
    x: 3,
    y: 6,
    w: 6,
    h: 5,
  });
  const full = Array.from({ length: 10 }, (_, y) =>
    newWidget("lap-table", { x: 0, y: y * 20, w: 12, h: 20 }),
  );
  assert.equal(findSpace(full), null);
});

test("resize clamps to minimum, maximum and remaining grid space without moving the panel", () => {
  const widget = newWidget("lap-table", { x: 2, y: 190, w: 6, h: 6 });
  const resize = (w: number, h: number) =>
    clampResize([widget], widget, { w, h });
  assert.deepEqual(resize(-100, -100), { x: 2, y: 190, w: 4, h: 4 });
  assert.deepEqual(resize(100, 100), { x: 2, y: 190, w: 10, h: 10 });
  assert.deepEqual(resize(1, 6), { ...widget.placement, w: 4 });
  assert.deepEqual(resize(6, 100), { ...widget.placement, h: 10 });
  assert.deepEqual(resize(NaN, 6), widget.placement);
  const top = newWidget("lap-table", { x: 0, y: 0, w: 6, h: 6 });
  assert.deepEqual(clampResize([top], top, { w: 100, h: 100 }), {
    x: 0,
    y: 0,
    w: 12,
    h: 20,
  });
});

test("resize stops at aspect limits and neighbors while leaving untouched axes fixed", () => {
  const chart = newWidget("stint-analysis", { x: 0, y: 0, w: 12, h: 7 });
  assert.deepEqual(clampResize([chart], chart, { w: 1, h: 7 }), {
    ...chart.placement,
    w: 6,
  });
  assert.deepEqual(clampResize([chart], chart, { w: 12, h: 100 }), {
    ...chart.placement,
    h: 14,
  });
  const table = newWidget("lap-table", { x: 0, y: 0, w: 4, h: 4 });
  const right = newWidget("lap-table", { x: 7, y: 0, w: 4, h: 4 });
  const below = newWidget("lap-table", { x: 0, y: 9, w: 4, h: 4 });
  assert.deepEqual(
    clampResize([table, right, below], table, { w: 12, h: 20 }),
    {
      x: 0,
      y: 0,
      w: 7,
      h: 9,
    },
  );
});

test("every widget stays valid at resize limits and repeated boundary requests are stable", () => {
  for (const [id, policy] of Object.entries(widgetCatalog)) {
    if (!policy.builderEnabled) continue;
    const widget = newWidget(id as WidgetId, {
      x: 0,
      y: 0,
      ...fitWidgetSize(id as WidgetId),
    });
    for (const w of [-100, widget.placement.w, 100]) {
      for (const h of [-100, widget.placement.h, 100]) {
        const box = clampResize([widget], widget, { w, h });
        assert.ok(canPlace([widget], widget.instanceId, box), id);
        const updated = { ...widget, placement: box };
        assert.deepEqual(clampResize([updated], updated, { w, h }), box, id);
        if (w === widget.placement.w) assert.equal(box.w, w);
        if (h === widget.placement.h) assert.equal(box.h, h);
      }
    }
  }
});

test("draft round trips keep widget options, placements, sections and instance independence", () => {
  const draft = emptyDraft("session-lookback");
  const options = { title: "Pace", metric: "speed_kph" };
  draft.name = "My layout";
  draft.sections[0].title = "Pace view";
  draft.sections[0].widgets.push(
    newWidget("telemetry-line-chart", { x: 2, y: 3, w: 8, h: 6 }, options),
  );
  options.title = "Unrelated edit";
  const config = draftToConfig(draft, "layout");
  const restored = draftFromLayout({
    id: "user:test",
    name: draft.name,
    source: "user",
    description: "",
    audience: draft.audience,
    schemaVersion: 2,
    updatedAt: "",
    config,
  });
  assert.equal(restored.sections[0].widgets[0].options?.title, "Pace");
  assert.deepEqual(restored.sections[0].widgets[0].placement, {
    x: 2,
    y: 3,
    w: 8,
    h: 6,
  });
  assert.equal(restored.sections[0].title, "Pace view");
  assert.equal(
    restored.sections[0].widgets[0].instanceId,
    draft.sections[0].widgets[0].instanceId,
  );
  assert.equal(draftError(restored), null);
  restored.sections[0].widgets[0].options!.title = "Changed";
  assert.equal(draft.sections[0].widgets[0].options?.title, "Pace");
});

test("empty and unnamed drafts cannot be saved", () => {
  const draft = emptyDraft("live-race");
  assert.match(draftError(draft)!, /name/);
  draft.name = "Race";
  assert.match(draftError(draft)!, /widget/);
});

test("factory row/column templates keep their arrangement when copied into the grid", () => {
  const record = {
    id: "builtin:test",
    name: "Factory",
    source: "builtin" as const,
    audience: "session-lookback" as const,
    schemaVersion: 1,
    updatedAt: "",
    config: {
      id: "template",
      sections: [
        {
          id: "one",
          layout: {
            type: "group" as const,
            direction: "row" as const,
            children: [
              {
                type: "group" as const,
                direction: "column" as const,
                children: [
                  {
                    type: "widget" as const,
                    widgetId: "telemetry-line-chart" as const,
                    minHeight: 280,
                  },
                  {
                    type: "widget" as const,
                    widgetId: "telemetry-line-chart" as const,
                    minHeight: 280,
                  },
                ],
              },
              {
                type: "widget" as const,
                widgetId: "brake-trace-chart" as const,
                width: "1/3" as const,
                minHeight: 580,
              },
            ],
          },
        },
      ],
    },
  };
  const draft = draftFromLayout(record, true);
  assert.equal(draft.name, "Factory copy");
  assert.deepEqual(
    draft.sections[0].widgets.map((widget) => widget.placement),
    [
      { x: 0, y: 0, w: 8, h: 5 },
      { x: 0, y: 5, w: 8, h: 5 },
      { x: 8, y: 0, w: 4, h: 10 },
    ],
  );
  assert.equal(draftError(draft), null);
  assert.equal(record.config.sections[0].layout.children[1].type, "widget");
});

test("every session widget has a usable default, explicit size policy and distinct content preview", () => {
  assert.equal(widgetCatalog["health-overview"].builderEnabled, false);
  assert.equal(widgetCatalog["sessions-summary"].builderEnabled, false);
  for (const [id, policy] of Object.entries(widgetCatalog)) {
    assert.ok(
      [
        "status",
        "trace",
        "brake",
        "pace",
        "stints",
        "laps",
        "track",
        "driver-cards",
        "tyre-timeline",
        "position-history",
        "notifications",
        "insights",
      ].includes(policy.previewKind),
    );
    assert.ok(
      [
        "platform",
        "telemetry",
        "strategy",
        "track",
        "replay",
        "race",
        "engineering",
      ].includes(policy.category),
    );
    assert.ok(
      policy.sizing.compactBelowPx > 0 && policy.sizing.shortBelowPx > 0,
    );
    assert.ok(
      policy.supportedAudiences.every((audience) =>
        ["session-lookback", "live-race"].includes(audience),
      ),
    );
    assert.ok(!policy.sizing.minAspect || policy.sizing.minAspect > 0);
    assert.ok(!policy.sizing.maxAspect || policy.sizing.maxAspect > 0);
    if (!policy.builderEnabled) continue;
    assert.ok(policy.supportedAudiences.length);
    assert.equal(policy.accessTier, 0);
    const size = fitWidgetSize(id as WidgetId);
    assert.equal(
      widgetSizeError(id as WidgetId, { x: 0, y: 0, ...size }),
      null,
      id,
    );
    assert.ok(widgetSizeError(id as WidgetId, { x: 0, y: 0, w: 2, h: 2 }));
  }
});

test("chart size and shape constraints apply to resizing and draft validation", () => {
  assert.match(
    widgetSizeError("stint-analysis", { x: 0, y: 0, w: 6, h: 12 })!,
    /wider/,
  );
  assert.match(
    widgetSizeError("lap-time-trend", { x: 0, y: 0, w: 4, h: 4 })!,
    /at least/,
  );
  const box = findSpace([], {}, "stint-analysis")!;
  assert.deepEqual(box, { x: 0, y: 0, w: 12, h: 7 });
  const widget = newWidget("stint-analysis", box);
  assert.equal(
    canPlace([widget], widget.instanceId, { ...box, w: 6, h: 12 }),
    false,
  );
  const draft = emptyDraft("session-lookback");
  draft.name = "Analysis";
  draft.sections[0].widgets = [
    newWidget("health-overview", { x: 0, y: 0, w: 6, h: 5 }),
  ];
  assert.match(draftError(draft)!, /platform/);
  draft.sections[0].widgets = [
    newWidget("replay-track-map", { x: 0, y: 0, w: 6, h: 5 }),
  ];
  assert.match(draftError(draft)!, /Replay only/);
});

test("optional maximum aspect ratios fit a taller layout without changing the policy", () => {
  const sizing = widgetCatalog["session-track-map"].sizing;
  const previous = sizing.maxAspect;
  try {
    sizing.maxAspect = 0.8;
    assert.match(
      widgetSizeError("session-track-map", { x: 0, y: 0, w: 6, h: 4 })!,
      /taller/,
    );
    const fitted = fitWidgetSize("session-track-map", { w: 6, h: 4 });
    assert.equal(
      widgetSizeError("session-track-map", { x: 0, y: 0, ...fitted }),
      null,
    );
    assert.equal(sizing.maxAspect, 0.8);
    const widget = newWidget("session-track-map", { x: 0, y: 0, w: 6, h: 14 });
    assert.deepEqual(clampResize([widget], widget, { w: 100, h: 14 }), {
      ...widget.placement,
      w: 6,
    });
    assert.deepEqual(clampResize([widget], widget, { w: 6, h: 1 }), {
      ...widget.placement,
      h: 13,
    });
  } finally {
    if (previous === undefined) delete sizing.maxAspect;
    else sizing.maxAspect = previous;
  }
});
