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
- `frontend/src/widgets/telemetry/SessionTelemetryWidgets.tsx`
- `frontend/src/widgets/replay/ReplayWidgets.tsx`

### Sessions integration helpers

- `frontend/src/features/sessions/session-layouts.ts`
- `frontend/src/features/sessions/SessionWorkspaceContext.tsx`
- `frontend/src/features/sessions/session-data.hooks.ts`

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

Simulation layouts:

- `builtin:replay-command`
- `builtin:replay-focus`

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

Instead it mounts an “Unavailable Widget” card.

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

The session-lookback widget family lives in `SessionTelemetryWidgets.tsx`.

Current widgets include:

- `TelemetryLineChartWidget`
- `BrakeTraceChartWidget`
- `LapTimeTrendWidget`
- `LapTableWidget`
- `SessionTrackMapWidget`

## Important telemetry widget behavior

- widgets read workspace context rather than receiving large prop trees
- widgets decide whether they should load based on driver and lap selection
- lap-scoped widgets show explicit empty states when `lap = all`
- telemetry queries are lazy and widget-specific
- simple SVG rendering is used for current charting needs

## Replay Widgets

The live-race widget family lives in `ReplayWidgets.tsx`.

Current widgets include:

- `ReplayTrackMapWidget`
- `ReplayDriverCardsWidget`

## Important replay widget behavior

- they consume the shared replay clock from workspace context
- they are allowed only in `live-race` audience layouts
- they query or derive only the data needed for the current replay view

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
