# Frontend Architecture

Back to [Backend Architecture](./02-backend-architecture.md)

## Current Frontend Stack

The frontend lives under `frontend/` and is a React single-page application.

Core building blocks currently visible in the codebase:

- React Router for navigation
- Axios for HTTP communication
- TanStack Query for server-state fetching and caching
- route-level pages plus shared layout components

## Current Structure

### App shell

The app shell lives under `frontend/src/app`.

Key responsibilities:

- global layout
- top-level navigation
- route registration
- shared shell UI such as header and sidebar

### Pages

The `frontend/src/pages` folder contains route-level screens.

Current state:

- home page is implemented as the main hub
- login and signup pages are implemented
- many product surfaces still render placeholder pages with directionally correct copy

### Data layer

The `frontend/src/data` area contains:

- `api/` for Axios API functions
- `queries/` for React Query hooks
- `contracts/` for frontend DTO typing
- `mappers/` for transforming API payloads into UI-specific shapes

This keeps network access and UI composition separate.

## Current Routing Model

The main route tree is defined in `frontend/src/app/router/routes.tsx`.

Current visible surfaces:

- `/`
- `/sessions`
- `/sessions/:sessionId`
- `/live`
- `/live/:sessionId`
- `/story-feed`
- `/standings`
- `/login`
- `/signup`
- `/system/health`

Important note: several routes already exist from a product/navigation perspective even though their page implementations are still placeholders.

## Current Backend Integration

The frontend currently communicates with the backend through `apiClient` in `frontend/src/data/api/client.ts`.

Current live integrations include:

- auth session and auth token flows
- session list and session detail reads

The backend now exposes more session endpoints than the frontend currently consumes, so the frontend data layer is expected to grow into:

- session catalog browsing
- selected-session import
- entry list views
- lap tables
- telemetry charts
- tick/replay consumers

## Design Direction

The frontend is moving toward a set of session-oriented surfaces:

- archive/session explorer
- session detail
- live race command surface
- future telemetry and metric widgets

This means the backend contract should remain resource-oriented and composable instead of returning giant page-specific payloads.

## Why The Current Frontend Shape Is Reasonable

- It is easy to add a new API hook without touching layout code.
- Page-level placeholder routing allows navigation and IA work to proceed before every backend contract is finished.
- The Axios plus React Query split is straightforward and easy to maintain.

## Near-Term Frontend Work Suggested By The Backend

- add API clients for the new session endpoints
- add typed DTOs for entries, laps, telemetry, and ticks
- replace placeholder session surfaces with archive/detail pages
- introduce chart and table components that can query one metric or one telemetry series at a time
