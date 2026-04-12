# Frontend Sessions Workspace

Back to [Frontend Architecture](../architecture/03-frontend-architecture.md)

## Purpose

The frontend sessions module owns the archive-style session explorer and the telemetry workspace.

It is responsible for:

- browsing the FastF1-backed session catalog
- importing a selected session into the backend cache
- opening a session-specific workspace
- expressing workspace state through URL search params
- resuming the last active workspace
- switching between lookback and simulation modes
- coordinating driver, lap, layout, and replay state for widgets

This is currently the richest real frontend domain in the project.

## Why This Module Is Central

The current product is session-centric.

The user journey already expects the frontend to support:

1. choose a season
2. choose a race weekend
3. choose one session
4. import or reuse it
5. select a mode
6. select drivers, laps, and a layout
7. render telemetry or replay widgets

Because of that, the sessions frontend is not just another page. It is the main place where:

- backend catalog data becomes user flow
- layout composition becomes live UI
- telemetry queries become contextual and lazy

## Current File Map

### Route pages

- `frontend/src/pages/SessionsExplorerPage.tsx`
- `frontend/src/pages/SessionWorkspacePage.tsx`
- `frontend/src/pages/sessions-page.css`

### Feature state and helpers

- `frontend/src/features/sessions/SessionWorkspaceContext.tsx`
- `frontend/src/features/sessions/session-data.hooks.ts`
- `frontend/src/features/sessions/session-layouts.ts`
- `frontend/src/features/sessions/session-resume.ts`
- `frontend/src/features/sessions/session-utils.ts`
- `frontend/src/features/sessions/session-workspace.search.ts`

### Data dependencies

- `frontend/src/data/contracts/sessions.contracts.ts`
- `frontend/src/data/contracts/layouts.contracts.ts`
- `frontend/src/data/queries/sessions.queries.ts`
- `frontend/src/data/queries/layouts.queries.ts`
- `frontend/src/data/api/sessions.api.ts`
- `frontend/src/data/api/layouts.api.ts`

### Widget dependencies

- `frontend/src/widgets/registry/dashboard.config.ts`
- `frontend/src/widgets/shared/DashboardRenderer.tsx`
- `frontend/src/widgets/telemetry/SessionTelemetryWidgets.tsx`
- `frontend/src/widgets/replay/ReplayWidgets.tsx`

## Surface Split

The frontend sessions module is split into two route surfaces.

## `/sessions` - explorer surface

The explorer is a fixed entry page for finding and preparing a session.

Its job is not to display telemetry. Its job is to get the user into the right workspace as cleanly as possible.

### Current responsibilities

- fetch the season catalog through `useSessionCatalogQuery(season)`
- group catalog entries by weekend
- let the user select year, race weekend, and session
- let the user choose `lookback` or `simulation`
- call `useImportSessionMutation()` when the user presses `Load session`
- navigate directly into `/sessions/:sessionId` after import succeeds
- auto-resume an already active workspace unless the user explicitly requests `?view=explorer`

### Important current UX detail

The explorer now uses two staged selectors:

1. `Season`
2. `Race weekend`

Only after the weekend is chosen does the session list appear. This avoids dumping a full-season session list into one giant scrolling block.

## `/sessions/:sessionId` - workspace surface

The workspace is the real telemetry environment.

Its job is to:

- load the imported session
- load entries and replay ticks when needed
- keep control state in the URL
- filter available layouts by audience
- avoid mounting telemetry until a layout is chosen
- host either lookback controls or replay controls
- render the selected layout into the main telemetry stage

This surface is where layouts become live dashboards.

## Workspace State Model

The workspace uses URL search params as the canonical state for user-visible controls.

## Search-param shape

Defined in `session-workspace.search.ts`:

- `mode`
- `layout`
- `drivers`
- `lap`

Represented in code as:

- `SessionWorkspaceSearchState`

Default state:

- `mode: "lookback"`
- `layoutId: null`
- `driverIds: []`
- `lap: "all"`

## Why URL state matters

Using the URL for these controls means:

- the current workspace can be linked
- refreshes preserve the main telemetry context
- layout, driver, and lap selection remain inspectable
- local resume storage can simply persist the same state shape

## Local resume state

`session-resume.ts` stores the currently active workspace in `localStorage` under:

- `pitwall.active-session-workspace`

Stored data includes:

- `sessionId`
- `state`
- `updatedAt`

This is why reopening the Sessions tab can resume the last active workspace instead of always dropping the user back into raw catalog browsing.

## Explorer-to-Workspace Flow

The import flow on `SessionsExplorerPage.tsx` is a core part of the module.

### Current sequence

1. user selects a catalog session
2. user selects `lookback` or `simulation`
3. `Load session` sends `season_year`, `round_number`, `session_name`, and `source_session_key`
4. backend imports the session or returns the cached one
5. frontend writes default workspace state to local resume storage
6. frontend navigates straight into `/sessions/:sessionId?...`

That direct navigation is important. The user does not need to perform a second “open workspace” step after the import finishes.

## Why `source_session_key` matters

The explorer forwards `source_session_key` from catalog items to import requests.

That solves an important precision problem:

- repeated testing sessions can share visible names like `Practice 1`
- the backend needs a stable source-specific session identity

Without that key, import precision breaks down on weekends that contain repeated session naming patterns.

## Workspace Data Loading Model

`SessionWorkspacePage.tsx` orchestrates several data sources.

## Base queries

Always or conditionally loaded:

- session detail via `useSessionQuery`
- entries via `useSessionEntriesQuery`
- user layouts via `useLayoutsQuery(authenticated)`
- ticks via `useSessionTicksQuery(..., mode === "simulation")`

## Control-support queries

For lookback mode, the page fetches lap lists for selected drivers so the lap selector can offer only valid lap numbers.

## Widget queries

The page itself does not fetch all telemetry up front.

Instead, widgets fetch their own data through session feature hooks, and only after:

- a valid layout is selected
- the widget is mounted
- the widget has enough control context

That is one of the most important performance and architecture decisions in the module.

## Session Workspace Context

`SessionWorkspaceContext.tsx` is the shared runtime state container for widgets.

It provides:

- `sessionId`
- full `session`
- all `entries`
- current `mode`
- current `audience`
- selected layout
- selected driver ids
- selected entry objects
- current lap selection
- replay controller state

This means widgets do not need to individually re-derive the same high-level workspace context.

## Replay controller

The replay controller inside the context owns:

- `ticks`
- `currentTimeMs`
- `isPlaying`
- `speedMultiplier`
- `minTimeMs`
- `maxTimeMs`
- `currentTick`
- `leaderEntry`
- `leaderLaps`

And actions:

- `togglePlayback`
- `setCurrentTimeMs`
- `setSpeedMultiplier`
- `resetPlayback`

This is the shared clock for simulation-mode widgets.

## Lookback vs simulation

The frontend explicitly supports two workspace modes.

## Lookback

Lookback mode is archive-oriented.

It allows:

- unlimited driver selection
- lap selection
- full-session widgets
- lap-scoped widgets

Widgets themselves decide whether they can work with `lap = all` or whether they need one specific lap.

## Simulation

Simulation mode is replay-oriented.

It uses:

- session ticks
- a local replay clock
- playback speed controls
- start, pause, and reset controls

It does not allow future-aware lookback widgets. Only `live-race` audience layouts and widgets are allowed here.

## Audience gating

The audience is derived from mode in `session-layouts.ts`:

- `lookback -> session-lookback`
- `simulation -> live-race`

This is what lets the future live race surface reuse the same audience rules without merging the two products into one page.

## Layout Resolution

`session-layouts.ts` merges:

- frontend built-in layouts
- backend user layouts

Then it:

- filters by audience
- validates widget references
- marks invalid saved layouts instead of crashing

That means the workspace can safely show built-ins for everyone and private layouts for authenticated users.

## Very Important Concept: layouts are not widgets

This distinction is central to the frontend sessions architecture.

### Widgets

Widgets are the individual renderable units:

- line chart
- lap table
- track map
- replay driver cards

They are defined in the widget registry and implemented as React components.

### Layouts

Layouts are compositions of many widgets arranged into sections and groups.

One layout can contain:

- one widget
- several widgets
- nested groups of widgets

The user chooses a layout first. The renderer then mounts the widgets referenced by that layout.

The workspace never treats a layout as if it were itself a widget.

## Stage and rail model

The loaded workspace uses a split layout:

- a smaller left rail for controls and layout picking
- a larger right stage for the mounted telemetry layout

This is intentional. Once a session is loaded, the telemetry surface should dominate the page, not the explorer controls.

## Session Data Hooks

`session-data.hooks.ts` gives widgets convenient multi-entry data access built on top of the workspace context.

Current hook families include:

- selected entry laps
- selected car telemetry
- selected position telemetry
- all-entry position telemetry

These hooks use `useQueries()` so widgets can request per-entry resources while still consuming the result as entry-keyed maps.

## Lazy loading model

The hooks are designed to respect widget-level `enabled` decisions.

This matters because:

- not every selected layout uses every dataset
- replay widgets should not force lookback data loads
- lap-scoped widgets should not load until a lap is chosen

## Boundaries

### Belongs here

- explorer and workspace route flow
- workspace URL state
- session resume behavior
- mode-to-audience mapping
- shared session workspace context
- feature-level telemetry hook composition

### Does not belong here

- raw Axios transport rules
- auth token handling
- widget registry definitions
- layout JSON schema ownership
- backend import and session persistence logic

Those concerns belong in the data layer, widget system, or backend modules.

## Current Strengths

- Real end-to-end archive workflow now exists
- URL state makes workspace behavior linkable and inspectable
- Layout selection cleanly gates widget mounting and telemetry fetching
- Replay mode has a shared clock instead of widget-local timing hacks
- Resume behavior makes the sessions area feel continuous rather than disposable

## Current Limitations

- No layout builder UI yet
- Replay control state is local and not shareable through the URL
- Some telemetry widgets still use simple SVG rendering and do not yet expose advanced chart interactions
- Large multi-driver selections are allowed, but can still feel heavy

## Future Work

- add a layout builder that saves the same `DashboardConfig` shape already used here
- extend replay widgets and stage chrome once the dedicated live race surface is built
- add more telemetry-oriented widgets without changing the explorer or workspace fundamentals
- consider more sophisticated caching or prefetching once widget count grows further
