# Frontend Widget System

Back to [Frontend Architecture](../architecture/03-frontend-architecture.md)

## Purpose

The frontend widget system owns reusable dashboard building blocks and the layout composition model that arranges them on screen.

It is responsible for:

- defining widget identities and capabilities
- defining the shape of dashboard layouts
- registering widget implementations
- rendering layout trees into real React components
- providing built-in dashboard and session layouts
- separating widget definitions from user-selectable layout composition

This module is what allows the product to behave like a configurable telemetry workspace instead of a pile of one-off pages.

## Why This Module Matters

The project now has two kinds of dashboard behavior:

- a home/dashboard-style overview surface
- a sessions workspace where users choose from layouts and then mount telemetry widgets

That requires a system that can answer two different questions cleanly:

1. what widgets exist?
2. how are widgets arranged for one particular screen?

The widget system exists to keep those questions separate.

## Current File Map

### Registry and types

- `frontend/src/widgets/registry/widget.types.ts`
- `frontend/src/widgets/registry/widget.registry.ts`
- `frontend/src/widgets/registry/dashboard.config.ts`

### Shared rendering infrastructure

- `frontend/src/widgets/shared/DashboardRenderer.tsx`
- `frontend/src/widgets/shared/WidgetCard.tsx`
- `frontend/src/widgets/shared/WidgetState.tsx`
- `frontend/src/widgets/shared/dashboard-renderer.css`

### Widget implementations

- `frontend/src/widgets/overlays/health-overview/HealthOverviewWidget.tsx`
- `frontend/src/widgets/overlays/sessions-summary/SessionsSummaryWidget.tsx`
- `frontend/src/widgets/telemetry/index.ts`
- `frontend/src/widgets/telemetry/models.ts`
- `frontend/src/widgets/telemetry/components/`
- `frontend/src/widgets/telemetry/utils/`
- `frontend/src/widgets/telemetry/widgets/`
- `frontend/src/widgets/telemetry/SessionTelemetryWidgets.tsx` as a compatibility export barrel
- `frontend/src/widgets/track-map/index.ts`
- `frontend/src/widgets/track-map/models.ts`
- `frontend/src/widgets/track-map/components/`
- `frontend/src/widgets/track-map/utils/`
- `frontend/src/widgets/track-map/widgets/`
- `frontend/src/widgets/replay/ReplayWidgets.tsx`

### Sessions integration helpers

- `frontend/src/features/sessions/session-layouts.ts`
- `frontend/src/features/sessions/SessionWorkspaceContext.tsx`
- `frontend/src/features/sessions/session-data.hooks.ts`

`session-data.hooks.ts` is the preferred widget data boundary for session widgets. Widget components should usually consume its resource hooks instead of calling session APIs or telemetry materialization APIs directly.

## Core Concepts

## Very Important Distinction: widgets and layouts are not the same

This project explicitly separates the two.

### Widgets

A widget is one renderable module.

Examples:

- `telemetry-line-chart`
- `lap-table`
- `session-track-map`
- `replay-driver-cards`

Each widget has:

- one id
- one React component
- metadata such as title and description
- optional audience restrictions

### Layouts

A layout is a composition of multiple widgets.

A layout can describe:

- one widget in one section
- several widgets side by side
- nested groups of widgets across many sections

Layouts do not render themselves directly. They are interpreted by `DashboardRenderer`, which looks up each widget id in the registry and mounts the actual widget components.

This distinction is the foundation of saved layouts, built-in layouts, and the future layout builder.

## Type System

The type model lives in `widget.types.ts`.

## Audience types

- `DashboardAudience = "session-lookback" | "live-race"`
- `SessionWorkspaceMode = "lookback" | "simulation"`

Audience exists because not every widget is safe in every runtime context.

Examples:

- lookback widgets can rely on full session history
- live-race widgets must behave correctly without future knowledge

## Widget types

Important types include:

- `WidgetId`
- `WidgetDefinition`
- `LayoutWidgetNode`
- `LayoutGroupNode`
- `DashboardSection`
- `DashboardConfig`
- `LayoutRecord`

## `WidgetDefinition`

Each registry entry contains:

- `id`
- `title`
- optional `description`
- optional `supportedAudiences`
- `component`

## `LayoutWidgetNode`

This is one placed widget inside a layout tree.

It includes:

- `widgetId`
- optional `options`
- width and height hints
- min and max size hints
- growth and class overrides

The `options` field is important because it lets one widget implementation be reused in multiple contexts.

Example:

- the telemetry line widget can render speed or throttle depending on `options.metric`

## `LayoutGroupNode`

Groups compose widget nodes recursively.

They define:

- direction
- gap
- child nodes

That gives the system enough flexibility to build rich dashboards without hardcoding each page layout in JSX.

## Registry Responsibilities

The widget registry lives in `widget.registry.ts`.

It is the canonical map from `WidgetId` to runtime widget behavior.

Current registry families:

- health overview widget
- sessions summary widget
- lookback telemetry widgets
- replay widgets

## Audience gating in the registry

Some widgets declare `supportedAudiences`.

Current pattern:

- telemetry widgets are limited to `session-lookback`
- replay widgets are limited to `live-race`
- generic overview widgets are not audience-restricted

This is how the system prevents invalid session-mode combinations before rendering.

## Built-in Layouts

Built-in layouts live in `dashboard.config.ts`.

## Home dashboard

`homeDashboardConfig` is the static overview configuration for the home/dashboard-style surface.

It currently mounts:

- `health-overview`
- `sessions-summary`

## Built-in session layouts

The frontend currently ships starter layouts directly in code.

Lookback layouts:

- `builtin:compare-lap`
- `builtin:session-trends`
- `builtin:stint-strategy`

Simulation layouts:

- `builtin:replay-command`
- `builtin:replay-focus`

`builtin:replay-command` also mounts `stint-analysis` as a replay-safe strategy
section. In simulation mode the widget only includes laps completed by the
current replay clock.

Each built-in layout is a `LayoutRecord` with:

- `id`
- `name`
- optional `description`
- `source`
- `audience`
- `schemaVersion`
- `config`
- `updatedAt`

That shape intentionally matches the saved-layout shape closely so built-ins and user layouts can be merged into one gallery.

## Shared Renderer

`DashboardRenderer.tsx` is the engine that turns layout config into rendered UI.

## Rendering flow

1. render optional dashboard hero
2. iterate sections
3. render each section header
4. recursively traverse layout nodes
5. mount widget groups or widget components

## Unknown widget behavior

If a layout references a widget id that is not registered in the current build, the renderer does not crash the page.

Instead it mounts an "Unavailable Widget" card.

That matters for:

- forward compatibility
- saved layout safety
- debugging broken configurations

## Widget shell components

### `WidgetCard.tsx`

Provides the consistent chrome for most widgets:

- title
- optional description
- body area

### `WidgetState.tsx`

Provides reusable visual states such as:

- loading
- empty
- error

This keeps widget implementations focused on data logic rather than repeating the same fallback markup.

## Telemetry Widgets

The session-lookback widget family lives under `frontend/src/widgets/telemetry`.

The module is split by responsibility:

- `models.ts` owns shared telemetry widget option and chart data types.
- `components/` owns reusable chart renderers such as the simple line chart,
  lap-time comparison chart, and stint analysis chart.
- `utils/` owns calculation helpers such as lap filtering, status
  classification, outlier detection, and reference-series generation.
- `widgets/` owns one widget component per file.
- `SessionTelemetryWidgets.tsx` remains only as a compatibility export barrel
  for older imports.

Current widgets include:

- `TelemetryLineChartWidget`
- `BrakeTraceChartWidget`
- `LapTimeTrendWidget`
- `StintAnalysisWidget`
- `LapTableWidget`

`SessionTrackMapWidget` is still exported through the telemetry barrel for
layout compatibility, but the implementation now lives in the shared
`track-map` module because the same renderer powers replay maps.

## Important telemetry widget behavior

- widgets read workspace context rather than receiving large prop trees
- widgets decide whether they should load based on driver and lap selection
- lap-scoped widgets show explicit empty states when `lap = all`
- telemetry queries are lazy and widget-specific, but materialization and per-entry fetching are centralized in session resource hooks
- widgets do not need to know which backend job endpoint prepares telemetry
- simple SVG rendering is used for current charting needs, while the track map
  has its own reusable top-down renderer

### Driver lap pace widget

`LapTimeTrendWidget` still uses the stable widget id `lap-time-trend` so saved
layouts remain compatible, but its current product role is driver lap pace
comparison rather than a bare trend line.

It reads `entry_laps` through `useWorkspaceEntryLapsResource` and does not need
telemetry materialization. The current chart supports:

- selected-driver lap-time lines
- lap numbers on the horizontal axis
- formatted lap times on the vertical axis
- hover values for exact lap time, delta, tyre, status, and position
- track-status summary chips showing status range, approximate sector, and
  duration when event timing is available
- reference comparison against visible average, visible best, or any selected
  driver
- clean-lap, pit-lap, SC/VSC/red, outlier, smoothing, and track-status-band
  controls
- summary values for fastest visible lap, best median, shown laps, and active
  reference

The filtering is frontend-side because the existing lap DTO already carries the
needed fields: pit markers, `track_status`, deleted/generated/accurate flags,
compound, tyre life, and lap position. The widget also reads
`/api/sessions/{session_id}/track-status-events` when available to make yellow,
SC, VSC, and red-flag bands more precise than lap-level status alone.

### Stint analysis widget

`StintAnalysisWidget` uses the stable lap rows rather than a separate stint API.
This fits the current backend model because `EntryLapDto` already includes:

- `stint_number`
- `compound`
- `tyre_life`
- pit in/out markers
- lap accuracy/deleted/generated flags
- `track_status`
- absolute `lap_number`

The widget groups selected-driver laps into stint series in the frontend and
plots them against absolute session lap number. This is important: stint 2 does
not restart at x-axis lap 0, it begins where that driver's previous stint ended
in the session.

The current widget supports:

- per-driver, per-stint visibility toggles
- compound-aware markers and labels
- clean-lap, pit-lap, SC/VSC/red, outlier, trend-line, and track-status-band
  controls
- hover values for exact lap time, stint lap number, tyre life, track status,
  and position
- track-status summary chips and shaded bands that use event timing when
  available, falling back to lap-level status when not
- summary values for best median stint, longest stint, highest positive
  degradation, and visible laps
- simulation/replay usage by hiding laps that have not completed by the current
  replay clock

Because this is derived from selected entries, it stays cheap for compare views.
A future backend route may still be useful for full-field strategy overviews,
but it is not required for this first selected-driver stint widget.

## Track Map Widgets

The track-map widget family lives under `frontend/src/widgets/track-map`.

It owns the top-down circuit renderer used by both:

- `SessionTrackMapWidget` for session lookback
- `ReplayTrackMapWidget` for simulation/replay layouts

The module is split by responsibility:

- `models.ts` owns track-map points, traces, bounds, and widget option types.
- `utils/geometry.ts` owns sample sorting, lap grouping, smoothing,
  downsampling, SVG path generation, heading calculation, bounds, camera
  viewBox generation, and placeholder-position filtering.
- `utils/circuit-corners.ts` adapts session circuit-corner DTOs into map turn
  markers.
- `utils/track-map-data.ts` converts position samples plus lap rows into
  render-ready lookback or replay map data.
- `components/TrackMapViewer.tsx` owns the shared SVG surface, zoom controls,
  focus selection, pack/driver follow mode, manual pan, racing-line toggles,
  previous-lap ghost lines, turn markers, start/finish marker, legend, and
  current car/dot rendering.
- `components/F1CarMarker.tsx` owns the simple top-down car sketch rendered
  when the map is zoomed in enough.
- `widgets/SessionTrackMapWidget.tsx` and `widgets/ReplayTrackMapWidget.tsx`
  adapt workspace data into the shared renderer.

### Why the map is now its own module

The original map connected full-session position samples in order. That was
useful as a smoke test, but it produced scribbled shapes because a full session
contains many laps over the same circuit. The new map first segments position
samples by lap, then uses one representative lap as the circuit outline.

This gives the product a stronger base for the future map work:

- selected-driver lookback maps render one lap's racing line, or a
  representative lap when the workspace lap selector is set to `all`
- replay maps render current-lap trails up to the replay clock and keep the
  previous lap available as a faint ghost line so lap transitions are visible
- if no drivers are selected in replay, the widget can show the full field
- the outline is chosen from the best available lap rather than from connected
  multi-lap session samples
- zoom is viewBox-based, so the camera stays top-down and does not rotate
- the focus selector can follow the pack or one selected driver
- dragging the SVG switches the camera to manual pan mode
- reset returns the camera to the full-circuit view
- low zoom still shows driver dots and compact labels, while higher zoom adds
  simple color-matched car sketches
- car sketch size is derived from circuit scale and damped by zoom so it grows
  predictably without overwhelming the track
- racing lines and previous-lap ghosts can be toggled independently from the
  current car markers
- FastF1 circuit-corner metadata is exposed through
  `GET /api/sessions/{session_id}/circuit-corners` and rendered as numbered
  turn markers when the source provides it

The current renderer uses the data available from FastF1-derived position
samples, `EntryLapDto` rows, and source-backed circuit-corner metadata. The
track surface is still derived from a representative lap rather than an
official vector circuit polygon; this keeps side-by-side car positions and
driver racing lines faithful to telemetry while leaving room for a richer
official track asset later.

## Widget Data Resource Hooks

Session widgets should use the shared hooks in `frontend/src/features/sessions/session-data.hooks.ts`.

The recommended hooks are:

- `useWorkspaceEntryLapsResource(options)`
- `useWorkspaceCarTelemetryResource(options)`
- `useWorkspacePositionTelemetryResource(options)`

The lower-level hooks remain available for older or exceptional widgets:

- `useSelectedEntryLapsMap`
- `useSelectedCarTelemetryMap`
- `useSelectedPositionTelemetryMap`
- `useAllPositionTelemetryMap`

The resource hooks are preferred because they combine driver resolution, scope resolution, telemetry materialization, polling, and final sample reads behind one widget-facing API.

## Choosing the right resource hook

Use `useWorkspaceEntryLapsResource` for widgets that need lap metadata rather than telemetry samples.

Good examples:

- lap tables
- lap time trends
- best lap summaries
- stint summaries derived from lap rows

Use `useWorkspaceCarTelemetryResource` for widgets that need car-channel telemetry.

Good examples:

- speed traces
- throttle traces
- brake traces
- RPM or gear charts
- DRS state widgets

Use `useWorkspacePositionTelemetryResource` for widgets that need track position samples.

Good examples:

- static track maps
- replay track maps
- driver trail widgets
- gap visualization that depends on position samples

## Resource hook options

Telemetry resource hooks accept `WorkspaceTelemetryResourceOptions`.

Important options:

- `entryIds`: explicit backend session entry ids to load
- `entryMode`: `selected` uses selected drivers, `all` uses every entry in the workspace
- `scope`: `auto`, `lap`, or `session`
- `requireLap`: prevents loading until a specific lap is available
- `lapNumber`: explicit lap override
- `offset` and `limit`: sample window controls
- `sessionTimeFromMs` and `sessionTimeToMs`: session-time window controls
- `enabled`: final widget-level gate

Entry lap resources accept the smaller `WorkspaceEntryResourceOptions` shape:

- `entryIds`
- `entryMode`
- `enabled`

## Scope behavior

`scope: "auto"` follows the workspace lap selector:

- `lap = all` becomes `scope: "session"`
- a specific lap becomes `scope: "lap"`

Use `scope: "lap"` with `requireLap: true` when a widget only makes sense for one lap, such as a lap comparison trace.

Use `scope: "session"` when the widget should work across the whole imported session, such as a session track map or replay widget.

## Resource hook return shape

Telemetry resource hooks return:

- `entryIds`
- `entries`
- `scope`
- `lapNumber`
- `query`
- `enabled`
- `ready`
- `isPreparing`
- `stage`
- `waitMessage`
- `dataByEntryId`
- `isLoading`
- `isError`

`dataByEntryId` is the main render input. It is keyed by backend session entry id, so widgets can pair each sample list with the matching `entries` item.

## Standard widget state pattern

Most telemetry widgets should follow this order:

1. Show `WidgetEmpty` if the required driver or lap selection does not exist.
2. Show `WidgetError` if `resource.isError` is true.
3. Show `WidgetEmpty` with `resource.waitMessage` if `resource.enabled && !resource.ready`.
4. Show `WidgetLoading` if `resource.isLoading`.
5. Render from `resource.dataByEntryId`.

This keeps the user informed while the backend worker prepares cache segments, and it keeps widgets consistent across lookback and simulation surfaces.

## Example: lap-scoped car telemetry widget

```tsx
const resource = useWorkspaceCarTelemetryResource({
  scope: "lap",
  requireLap: true,
  limit: 5000,
});

if (!resource.lapNumber) {
  return <WidgetEmpty message="Choose one lap to compare telemetry." />;
}

if (resource.isError) {
  return <WidgetError />;
}

if (resource.enabled && !resource.ready) {
  return <WidgetEmpty message={resource.waitMessage} />;
}

const samplesByEntryId = resource.dataByEntryId;
```

## Example: full-session position widget

```tsx
const resource = useWorkspacePositionTelemetryResource({
  entryMode: "all",
  scope: "session",
  limit: 20000,
});

if (resource.enabled && !resource.ready) {
  return <WidgetEmpty message={resource.waitMessage} />;
}

const traces = resource.entries.map((entry) => ({
  entry,
  samples: resource.dataByEntryId[entry.id] ?? [],
}));
```

## Why widgets should not call materialization APIs directly

Materialization is an implementation detail of preparing telemetry data. A widget should express what it needs:

- entries
- car or position data
- session or lap scope
- optional limits and time windows

The session resource hooks translate that need into backend cache preparation and telemetry reads. That keeps new widgets small, consistent, and easier to migrate if the backend cache strategy changes again later.

## Replay Widgets

The live-race widget family is split across `ReplayWidgets.tsx` and the shared
`track-map` module.

Current widgets include:

- `ReplayTrackMapWidget`, implemented in `frontend/src/widgets/track-map`
- `ReplayDriverCardsWidget`

## Important replay widget behavior

- they consume the shared replay clock from workspace context
- they are allowed only in `live-race` audience layouts
- they query or derive only the data needed for the current replay view
- they can reuse the same full-session telemetry resources as lookback widgets because simulation and lookback share one imported session identity

This keeps replay behavior consistent across different simulation layouts.

## User Layout Integration

The widget system also supports saved user layouts.

Those are not defined in the registry.

Instead:

- the backend stores layout JSON
- the frontend loads those layout records
- `session-layouts.ts` converts them into `LayoutRecord`
- the system validates widget references and audience compatibility

This means the backend stores composition, while the frontend remains the owner of runtime widget behavior.

## Validation Rules

`session-layouts.ts` currently validates that:

- every referenced widget id exists in `widgetRegistry`
- every widget is compatible with the target layout audience

If validation fails:

- the layout is marked invalid
- the UI stays stable
- the user can choose another layout

That is exactly the kind of failure handling needed before a layout builder exists.

## Boundaries

### Belongs here

- widget ids and definitions
- dashboard layout schema
- built-in layout definitions
- layout rendering
- widget runtime mounting
- audience compatibility rules

### Does not belong here

- API transport logic
- direct telemetry materialization orchestration inside individual widgets
- route navigation
- session import flow
- auth token behavior
- backend layout persistence rules

Those belong in the data layer, route pages, or backend modules.

## Current Strengths

- Clear separation between renderable widget units and saved layouts
- Safe fallback behavior for invalid or missing widgets
- Audience model already prepares the codebase for future live-race reuse
- Layout config is expressive enough for real telemetry dashboards without being overly complex

## Current Limitations

- No visual layout builder exists yet
- Widget options are loosely typed as `Record<string, unknown>`
- Rendering is intentionally simple and not yet optimized for extremely large dashboards
- Some telemetry presentation is still basic SVG rather than a richer charting library

## Future Work

- add a layout builder that emits the same `DashboardConfig` structure
- strengthen widget option typing where the registry needs more validation
- introduce richer widget metadata if discovery, editing, and tooling require it
- consider schema migration helpers if layout versions become more complex
