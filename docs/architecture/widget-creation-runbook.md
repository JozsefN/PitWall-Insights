# Widget creation runbook

This is the implementation contract for session dashboard widgets in PitWall Insights. Complete every applicable step before offering a widget in the builder. A widget is a reusable analysis panel; a layout is a saved dashboard document; a group is a vertical block containing a grid of panels. All groups appear together, in stored order, on one scrolling dashboard. Groups are not tabs, alternative layouts, or data scopes. `sections` is retained as the storage/API field name for compatibility.

## 1. Define the behavior before writing the component

Write down the stable widget id, one analysis question, supported audiences, data resources, option types/defaults, units, empty/loading/error behavior, smallest readable size, shape restrictions and compact/short behavior. State explicitly whether the widget needs a selected driver, a specific lap, or the replay clock.

Audience meanings:

- `session-lookback`: completed-session analysis; full-session and selected-lap queries are possible.
- `live-race`: replay-compatible information bounded by the replay clock. Do not display future laps or future positions.

Session widgets must not contain platform administration, service health, account management, or import-volume information. Platform widgets can remain registered for other pages with `builderEnabled: false` and no session audiences.

## 2. Add exactly one policy entry to the shared catalog

Edit `shared/dashboard-widgets.json`. This is the policy authority for both the browser and backend. Do not add a second Python list of widget ids, audience rules, or sizes.

Example entry (replace the id, text, preview kind and measured sizes):

```json
"example-analysis": {
  "title": "Example Analysis",
  "description": "Describe the information provided, not the implementation.",
  "category": "telemetry",
  "previewKind": "trace",
  "builderEnabled": true,
  "supportedAudiences": ["session-lookback"],
  "accessTier": 0,
  "sizing": {
    "minW": 5, "minH": 4,
    "maxW": 12, "maxH": 20,
    "defaultW": 6, "defaultH": 5,
    "minAspect": 1.25,
    "compactBelowPx": 420,
    "shortBelowPx": 340
  },
  "defaultOptions": { "title": "Example Analysis" }
}
```

Allowed categories are `platform`, `telemetry`, `strategy`, `track`, `replay`. `accessTier` is `0` for Free, or `1`, `2`, `3` for future subscription tiers. All current widgets are Free. A paid label is not entitlement enforcement: before adding a paid widget, implement trusted server entitlement checks on layout writes and data reads. Never trust a submitted tier or client-side disabled button as authorization.

`WidgetId` is derived from the JSON keys in `widget.types.ts`. Adding a catalog id makes the TypeScript runtime component map incomplete until step 4 is done. New categories or preview kinds also require extending `WidgetPolicy` and implementing their presentation.

Sizing units and checks:

- The design viewport is 1200 pixels wide, with 12 columns, 48-pixel row height, and 12-pixel gaps. These values come from the catalog's `grid` object. Do not change them for an individual widget.
- Placement is `{x, y, w, h}` in integer grid cells. Coordinates start at zero. `x + w <= 12`, `y + h <= 200`, `2 <= w <= 12`, `3 <= h <= 20`.
- `minW`, `minH`, `maxW`, `maxH` further restrict those global bounds. `defaultW/defaultH` must be valid, readable and within all limits.
- Optional `minAspect` and `maxAspect` restrict **pixel width divided by pixel height at the design viewport**, not `w/h` in cells. For a placement, width is `w * ((1200 + 12) / 12) - 12`; height is `h * (48 + 12) - 12`.
- `minAspect` makes a panel wide enough for its chart. `maxAspect` prevents it becoming excessively wide and shallow. Omit unnecessary restrictions for flexible content. An impossible interval/default must fail tests before merge.
- `compactBelowPx` is the runtime panel width threshold. `shortBelowPx` is its runtime height threshold. They are applied to the actual panel, not the browser window. Both are strict less-than comparisons.
- `fitWidgetSize` chooses an initial size. Editor `clampResize` keeps the top-left corner fixed and clamps pointer, keyboard and numeric resizing to the nearest valid size in the requested direction. Minimum/maximum sizes, aspect ratios, grid bounds and neighboring panels all act as stops; untouched axes stay fixed. Repeated requests at a stop do not create undo history. `widgetSizeError` and Python `validate_widget_size` still reject invalid saved documents. A preview uses the actual saved placement, including any visible gap, rather than packing panels into an invented layout.

The editor scales the 1200-pixel design surface to fit available space. Pointer deltas must be divided by the displayed scale; do not introduce an independent drag coordinate system. The whole-dashboard preview and chooser thumbnails use the same placements and group order. Runtime dashboards reflow into a vertical stack below a 900-pixel dashboard content width.

## 3. Implement the data boundary

Use these layers in order:

1. Add/extend typed response contracts under `frontend/src/data/contracts`.
2. Put HTTP transport under `data/api`; use the existing `apiClient` so authentication is applied consistently.
3. Put cache keys, enabled conditions and invalidation under `data/queries`.
4. Put session coordination/derived values in the relevant feature hooks. Existing session resources are in `features/sessions/session-data.hooks.ts`; reuse the workspace lap/car/position resource hooks so materialization, readiness and cache behavior stay coordinated.
5. Read selected entries, lap scope and replay time through `useSessionWorkspace()` in the runtime widget.

Do not request heavy telemetry when prerequisites are absent. Driver/lap changes must change the resource key. Do not poll per widget when a shared workspace query already owns the resource. Do not request telemetry from the catalog, blueprint, layout thumbnail, or editor. The editor is independent of a loaded session.

For live/replay support, bound data and derived values to the current replay clock. Reset or recompute local state when the session changes. Preserve driver colors and the app's unit/formatting helpers.

## 4. Implement and register the runtime component

Place the component in the existing owning widget family, for example `widgets/telemetry/widgets/ExampleAnalysisWidget.tsx`. Its public signature is:

```tsx
export function ExampleAnalysisWidget({ options }: {
  options?: Record<string, unknown>;
}) {
  // Parse validated options, then read session hooks unconditionally.
  // Render a meaningful prerequisite/loading/error/empty state or the content.
}
```

Define a typed options interface and normalize defaults. Respect `options.title` when it is a string; otherwise use the catalog's default title. No React component, callback, DOM node, token, session id or driver selection belongs in persisted options. Session/driver/lap selections belong to the workspace, not the layout.

Use `WidgetCard`, `WidgetEmpty`, `WidgetLoading` and `WidgetError`. Call hooks in a stable order before conditional returns. Distinguish missing prerequisites from loading, failure and a successfully loaded empty result. Keep presentation/calculation helpers pure and independently testable.

Import the component in `widgets/registry/widget.registry.ts` and add it to `components` under its catalog id. The map uses `satisfies Record<WidgetId, WidgetDefinition["component"]>`; the build must fail for a missing component. Do not create another renderer or a second widget registry.

All runtime widgets are wrapped by `ResponsiveWidgetFrame` in `DashboardRenderer`. Do not duplicate that wrapper inside a widget. It supplies `data-density`, `data-height`, the named CSS container and the `useWidgetSize()` context.

## 5. Implement responsive behavior deliberately

Use `useWidgetSize()` from `widgets/shared/widget-size.ts` when component structure needs to change. It returns `{compact, short}` and also has safe defaults when no dashboard frame exists. Call it unconditionally with other hooks. Use scoped CSS in `widgets/shared/widget-responsive.css` for presentation changes; scope widget-specific rules with `[data-widget="example-analysis"]` or `[data-panel-kind="..."]`.

Required behavior:

- Width below `compactBelowPx`: keep the title, primary value/plot, units and essential actions; wrap controls; reduce optional detail. Do not shrink text until it becomes illegible.
- Height below `shortBelowPx`: preserve the primary result; omit optional summaries; put secondary controls in an accessible disclosure or scrolling detail area. `StintAnalysisWidget` demonstrates a disclosure that starts closed in short mode but can be opened by the user.
- Growth: use additional width/height for meaningful columns, series, rows, cards or plot area, rather than stretching the title/empty message.
- Charts: maintain readable legends/axes and hover coordinates when resized. Keep filtering reachable. Only optional axis titles/summaries may disappear.
- Tables: keep driver, lap and time in compact mode; hide optional columns or provide a clear scroll/detail alternative. Essential columns must not silently disappear.
- Maps: preserve circuit proportions, reflow camera controls and keep focus/reset accessible. Do not stretch the circuit to fill a rectangle.
- Repeated cards: change column count based on the panel, keeping a readable minimum card width.

The current policies are:

| Widget | Minimum cells | Default cells | Minimum aspect | Adaptation |
| --- | --- | --- | --- | --- |
| Telemetry Line Chart | 5 × 4 | 6 × 5 | 1.25 | Compact legend/controls; short plot mode |
| Brake Trace | 3 × 3 | 6 × 4 | 0.55 | Step trace can use a narrower shape |
| Driver Lap Pace | 5 × 4 | 8 × 6 | 1.25 | Wrapped filters; optional summary omitted when short |
| Stint Analysis | 6 × 5 | 12 × 7 | 1.4 | Wide plot; short-mode visibility disclosure |
| Lap Table | 4 × 4 | 6 × 6 | None | Compact driver/lap/time columns; more rows with height |
| Session Track Map | 3 × 4 | 6 × 6 | None | Circuit aspect retained; camera controls reflow |
| Replay Track Map | 3 × 4 | 8 × 7 | None | Same map rules; replay-clock positions |
| Replay Driver Cards | 3 × 4 | 4 × 6 | None | Responsive card columns and compact statistics |

All currently have maximum 12 × 20 cells, compact threshold 420 pixels and short threshold 340 pixels. Verify the JSON when changing a policy; the table is documentation, not a second authority.

## 6. Implement its structural preview

Add or reuse the correct `previewKind` in `WidgetBlueprint.tsx`. Reuse only when it truly describes the same visual structure. A map must look like a map, a table like a table, and stint analysis like compound windows/pace. Never reuse a generic line drawing merely to fill a new panel.

`WidgetBlueprint` receives `widgetId`, `options`, design-pixel `width/height` and optional `header`. It must be deterministic, side-effect free and independent of session hooks, providers and network. Use illustrative driver names and clearly illustrative values. Respect the title, relevant options, compact threshold, proportions and optional elements of the runtime component. Use proper SVG view boxes; maps preserve aspect while plots can fill their available plot area.

The editor adds its own draggable title/tier bar and uses `header={false}` for the body. Layout previews include the runtime-style title. `LayoutPreview` composes all groups into one SVG, while `DesignScale` handles the editable surface's display scale. Do not introduce persistent duplicate preview panes. A whole preview exposes one accessible image label; nested decorative SVGs stay hidden from assistive technology.

Check the blueprint at minimum size, default size, full width, compact width, short height and a tall/flexible size. It must show what information the panel provides, not pretend to show live data.

## 7. Add option settings and server validation

Add widget-specific settings to `features/dashboards/PanelSettings.tsx`, or extract a typed family-specific settings component if this grows. Preserve unrelated options when changing one option. Never persist cosmetic editor state, illustrative preview values or access badges into the layout.

The API automatically reads identity, eligibility, audiences and geometry rules from the shared JSON. Add validations for new option keys in `backend/modules/dashboard_layouts/domain/validation.py`, keyed to the widget if necessary. Current shared option checks cover string titles/units/metric labels, boolean `requiresLap`, and supported telemetry metrics. Numeric settings need finite bounds; enums need explicit values. Reject invalid input with a `ValueError`, which the route converts to HTTP 400. Invalid model fields may return 422. Do not allow a malformed option to crash a React render after saving.

Do not alter the meaning of existing widget ids/options in place. For an incompatible change, document migration/compatibility behavior and keep old saved layouts readable. Do not edit/delete factory layouts through personal-layout APIs. Optional changes to factory templates belong in `dashboard.config.ts` and need a deliberate review.

## 8. Test before declaring the widget available

Add tests for pure calculations and for its policy/defaults. Required cases:

1. Default placement passes frontend and Python validation.
2. Below-minimum width/height, above-maximum size, invalid aspect, bounds and overlap fail.
3. Optional maximum aspect works if configured; fitting does not mutate the policy.
4. Audience mismatch and platform eligibility are rejected by the server, not just hidden by the UI.
5. Missing prerequisites, loading, API failure, empty data and populated content render correctly.
6. Compact/short transitions work when **the panel** changes size in a fixed browser viewport. Restore the space and verify details return. Disclosures remain operable.
7. Blueprint kind/title/options match the runtime panel and make no telemetry requests.
8. Add, drag, resize, undo/redo, save, reload and edit preserve options and geometry; factory copies remain independent.
9. The widget survives all-groups overview and group reordering without changing its data scope.
10. Keyboard handles, labels, focus, alternate Add/numeric controls and a narrow viewport work.

Run the existing checks from `frontend`:

```powershell
npm run test
npm run build
npm run lint
```

With the API running, from `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

With an imported session and the production preview running on 4173, from the repository root:

```powershell
$env:PITWALL_FRONTEND_URL = 'http://127.0.0.1:4173'
python frontend/tests/layout-builder.e2e.py
```

The browser suite creates isolated test accounts and cleans them up. It writes screenshots under the OS temporary `pitwall-layout-builder-e2e` directory. Add a screenshot/test for the new widget's smallest readable size and compact mode; inspect it, not just the absence of overflow.

## 9. Package and document the result

The backend reads `shared/dashboard-widgets.json` relative to the repository root. Include the `shared` directory alongside `backend` when deploying backend source. The frontend bundles its copy during build. Deploy both from the same revision, and restart the backend after changing the JSON policy (Python-only auto-reload need not notice JSON changes).

No database migration is needed merely to register a widget or change its preview. Persisted documents remain the existing version-2 grid schema. New tables, incompatible document changes or entitlement data require their own migration/compatibility design.

Update the architecture notes, this widget table if necessary, validation report and any factory template that intentionally uses the widget. Record data costs, replay bounds, option defaults and important limitations. A widget is complete when runtime behavior, preview, policies, API validation and tests agree.

Implementation references: [MDN container queries](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Containment/Container_queries) and [MDN container types](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/container-type). The app additionally uses `ResizeObserver` to expose the shared policy thresholds to React behavior.
