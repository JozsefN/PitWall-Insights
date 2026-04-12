# Frontend

The frontend is a React 19 single-page application for PitWall-Insights.

It currently provides:

- the shared app shell and navigation
- auth entry screens
- the session explorer
- the session telemetry workspace
- the diagnostics surface
- widget-driven dashboard rendering for overview, telemetry, and replay layouts

## Stack

- React 19
- React Router 7
- TanStack Query 5
- Axios
- TypeScript
- Vite
- Tailwind v4 plus project CSS variables and route styles

## Main Commands

From `frontend/`:

```bash
npm run dev
npm run lint
npm run build
npm run preview
```

## Environment

The shared API client reads:

- `VITE_API_BASE_URL`

If it is not set, the frontend falls back to:

- `http://localhost:8000`

## Structure

### `src/app`

Bootstrap, providers, router, and shell layout.

### `src/data`

HTTP client, DTO contracts, API wrappers, query hooks, and mappers.

### `src/features`

Feature-level orchestration, currently centered on:

- `auth`
- `sessions`

### `src/pages`

Route screens and screen-specific CSS.

### `src/widgets`

Widget registry, shared renderer, overview widgets, telemetry widgets, and replay widgets.

## Frontend Documentation

Architecture entry points:

- [Architecture Home](../docs/architecture/README.md)
- [Frontend Architecture](../docs/architecture/03-frontend-architecture.md)

Frontend module reference:

- [Frontend App Shell](../docs/modules/frontend-app-shell.md)
- [Frontend Data Layer](../docs/modules/frontend-data-layer.md)
- [Frontend Auth](../docs/modules/frontend-auth.md)
- [Frontend Sessions Workspace](../docs/modules/frontend-sessions.md)
- [Frontend Widget System](../docs/modules/frontend-widget-system.md)

## Important Current Architectural Rules

### Layouts and widgets are not the same

Widgets are the individual renderable blocks.

Layouts are compositions of one or more widgets arranged into sections and groups.

The workspace selects a layout first, then the dashboard renderer mounts the widgets referenced by that layout.

### Sessions workspace state is URL-driven

The current session workspace uses search params for:

- `mode`
- `layout`
- `drivers`
- `lap`

This makes lookback and simulation state shareable and reload-safe.

### Built-in and saved layouts both exist

Built-in layouts live in frontend code.

Saved layouts are fetched from the backend for authenticated users and merged into the same gallery at runtime.

### Telemetry widgets are lazy

The workspace does not eagerly fetch every dataset.

Telemetry and replay widgets fetch only when:

- a compatible layout is selected
- the widget is mounted
- the current control state makes that widget meaningful

## Current Key Surfaces

- `/`
- `/sessions`
- `/sessions/:sessionId`
- `/login`
- `/signup`
- `/system/health`

Other routes such as `/live`, `/story-feed`, and `/standings` already exist in the shell and navigation, but some are still placeholder implementations.

## Notes for Contributors

- Prefer adding transport logic under `src/data` rather than calling Axios directly from pages.
- Prefer feature hooks and contexts for rich session behavior instead of pushing that logic into widgets or route files alone.
- Keep widget definitions and layout composition separate.
- Use the docs under `docs/modules/` when deciding where new frontend responsibilities belong.
