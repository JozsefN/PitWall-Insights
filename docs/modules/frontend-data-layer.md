# Frontend Data Layer

Back to [Frontend Architecture](../architecture/03-frontend-architecture.md)

## Purpose

The frontend data layer is the boundary between the React UI and the backend HTTP API.

It is responsible for:

- configuring the shared Axios client
- defining typed DTO contracts
- exposing thin endpoint wrappers
- providing TanStack Query hooks
- mapping backend response shapes into UI-friendly status models where needed

The data layer exists so route pages and widgets do not need to know how URLs, auth headers, query keys, or request details are constructed.

## Why This Module Matters

This project is already moving beyond simple page fetches. It now has:

- auth state
- health diagnostics
- session catalog browsing
- session import
- entry, lap, telemetry, and replay data
- user-owned layout persistence

Without a dedicated data layer, those responsibilities would quickly leak into pages and widgets, making the codebase harder to extend and much more fragile.

## Current File Map

### Shared client

- `frontend/src/data/api/client.ts`

### API function groups

- `frontend/src/data/api/auth.api.ts`
- `frontend/src/data/api/health.api.ts`
- `frontend/src/data/api/ingestion.api.ts`
- `frontend/src/data/api/normalization.api.ts`
- `frontend/src/data/api/feature-metrics.api.ts`
- `frontend/src/data/api/story-feed.api.ts`
- `frontend/src/data/api/sessions.api.ts`
- `frontend/src/data/api/layouts.api.ts`

### Typed contracts

- `frontend/src/data/contracts/auth.contracts.ts`
- `frontend/src/data/contracts/health.contracts.ts`
- `frontend/src/data/contracts/module-health.contracts.ts`
- `frontend/src/data/contracts/sessions.contracts.ts`
- `frontend/src/data/contracts/layouts.contracts.ts`

### Query hooks

- `frontend/src/data/queries/auth.queries.ts`
- `frontend/src/data/queries/health.queries.ts`
- `frontend/src/data/queries/module-health.queries.ts`
- `frontend/src/data/queries/sessions.queries.ts`
- `frontend/src/data/queries/layouts.queries.ts`

### Mappers

- `frontend/src/data/mappers/health.mapper.ts`
- `frontend/src/data/mappers/sessions.mapper.ts`

## Layering Model

The data layer follows a clear stack.

### Contracts

Contracts are the typed description of payloads the frontend expects to send or receive.

They answer:

- what fields exist
- which fields may be optional or nullable
- what the frontend believes the backend shape to be

### API functions

API files are thin wrappers over `apiClient`.

They answer:

- which endpoint to call
- which params to send
- which DTO type the response resolves to

They should stay boring. They are not the place for widget-specific UI rules.

### Query hooks

Query hooks adapt the API functions to TanStack Query.

They answer:

- what the query key is
- when the request is enabled
- whether the interaction is a query or mutation
- which invalidations should happen after mutations

### Mappers

Mappers are used when the backend payload is not the exact shape the UI wants to render directly.

This is currently light, but it is an important separation point as the product grows.

## Shared Client Responsibilities

`frontend/src/data/api/client.ts` defines the shared Axios instance.

## Current client behavior

- base URL comes from `VITE_API_BASE_URL`
- fallback base URL is `http://localhost:8000`
- `Content-Type` defaults to `application/json`
- every request checks `localStorage` for `auth_token`
- if a token exists, it is attached as `Authorization: Bearer <token>`

This is the entire frontend auth transport strategy today.

## Why the interceptor matters

The interceptor keeps feature code simple.

Pages and widgets do not need to manually forward the token on every request. They only need to rely on the shared client.

## Contract Groups

## Auth contracts

`auth.contracts.ts` defines request and response types for:

- sign up
- log in
- auth session lookups

## Health contracts

`health.contracts.ts` and `module-health.contracts.ts` define:

- root service health
- delivery API health
- module-specific health response shapes

These are especially important for the diagnostics page, where several backend module health surfaces are composed into a single frontend report.

## Session contracts

`sessions.contracts.ts` is currently one of the most important frontend contract files.

It covers:

- session catalog items
- session import requests
- imported session detail
- session entries
- entry laps
- session ticks
- car telemetry samples
- position telemetry samples
- telemetry query parameters

Important current details:

- catalog items carry `source_event_key` and `source_session_key`
- import requests can forward `source_session_key`
- telemetry query params support `lap_number`, `session_time_from_ms`, and `session_time_to_ms`

Those details are what make the session explorer and workspace precise enough for testing weekends, replay, and per-widget lazy querying.

## Layout contracts

`layouts.contracts.ts` defines the persisted shape for user-owned layouts.

It intentionally references widget-system types:

- `DashboardAudience`
- `DashboardConfig`

That is an important architectural choice. The backend stores layout composition data, but the frontend remains the owner of widget definitions and rendering behavior.

## API Surface by Concern

## Auth APIs

`auth.api.ts` exposes:

- `getAuthHealth`
- `getAuthSession`
- `signup`
- `login`
- `logout`

Notably, `logout` is frontend-only today and simply clears `localStorage`.

## Health APIs

The health API files expose the diagnostics endpoints used by `SystemHealthPage`.

This includes:

- root health
- delivery API health
- auth health
- ingestion health
- normalization health
- feature metrics health
- story feed health

These files are important even though some of the user-facing product surfaces are still placeholders, because diagnostics already helps validate the backend stack.

## Sessions APIs

`sessions.api.ts` is the core data API for the telemetry archive flow.

It currently exposes:

- list imported sessions
- fetch FastF1 session catalog
- import one selected session
- fetch session detail
- fetch session entries
- fetch entry laps
- fetch entry car telemetry
- fetch entry position telemetry
- fetch replay ticks

These functions are intentionally resource-oriented. The frontend assembles pages from several small queries rather than expecting one giant page-shaped response.

## Layout APIs

`layouts.api.ts` exposes authenticated CRUD for user layouts:

- list
- create
- update
- delete

Built-in layouts are not fetched from the backend. They stay in frontend code. The layout API is only for user-owned saved layouts.

## Query Hook Responsibilities

The query hook layer standardizes how the frontend talks to the server.

## Naming pattern

The codebase currently follows a predictable pattern:

- `useXQuery`
- `useYMutation`

This makes it easy to discover the query surface from feature code.

## Query key strategy

The keys are structured by resource hierarchy, for example:

- `["sessions"]`
- `["sessions", "catalog", season]`
- `["sessions", sessionId]`
- `["sessions", sessionId, "entries"]`
- `["sessions", sessionId, "entries", entryId, "laps"]`
- `["sessions", sessionId, "entries", entryId, "telemetry", "car", query]`

That matters for:

- deduplication
- cache correctness
- targeted invalidation
- debugging

## Mutation invalidation

Layout mutations invalidate `["layouts"]` after success.

That is currently enough because saved layout CRUD is scoped to a single list surface.

## Enabling conditions

The query layer uses `enabled` flags heavily.

Examples:

- session detail only fetches when `sessionId` exists
- entry telemetry only fetches when both `sessionId` and `entryId` exist
- layout queries only run when the user is authenticated
- replay tick queries only run in simulation mode

This pattern is one of the main reasons the workspace avoids unnecessary backend traffic.

## Mapper Responsibilities

The mapper layer is still small, but it already shows an important pattern.

### `health.mapper.ts`

This file turns raw health responses into frontend-friendly status categories such as:

- healthy
- degraded
- down
- unknown

That keeps rendering code much cleaner.

### `sessions.mapper.ts`

This file exists as an extension point for future session-focused projections. Even when mapping is still light, the architectural slot is important.

## Boundaries

### Belongs here

- DTO shapes
- endpoint wrappers
- query keys
- query enablement rules
- cache invalidation rules
- response normalization for frontend-specific status models

### Does not belong here

- route composition
- UI layout decisions
- workspace control logic
- widget rendering
- chart generation

Those belong in `pages`, `features`, or `widgets`.

## Current Strengths

- Clear separation between transport, typing, and query orchestration
- Query keys are readable and resource-oriented
- Contracts already cover telemetry and replay data in enough detail for serious frontend work
- The layout persistence surface is ready before the layout builder itself exists

## Current Limitations

- Error handling is still mostly per-screen rather than standardized across all APIs
- There is no shared response-to-toast or response-to-user-feedback system yet
- The mapper layer is still light, so some UI shaping still happens in feature code
- Auth token storage is intentionally simple and does not include refresh logic

## Future Work

- add stronger shared error modeling where the UI needs more precise recovery behavior
- introduce telemetry-specific helper types if chart widgets need richer query composition
- expand mapper usage as the story feed and standings surfaces become real
- document query-key conventions more formally if the data layer grows much larger
