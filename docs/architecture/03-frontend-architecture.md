# Frontend Architecture

Back to [Architecture Home](./README.md)

## Purpose

The frontend lives under `frontend/` and is a React single-page application.

Its job is to turn backend resources into a motorsport-focused operational interface with:

- a shared app shell
- typed data access
- session explorer and telemetry workspace flows
- reusable widget-driven dashboards

The frontend is no longer just placeholder scaffolding. It already contains one full archive workflow and the foundations for reusable session and live-race surfaces.

## Current Frontend Stack

Core frontend technologies currently visible in the codebase:

- React 19
- React Router 7
- TanStack Query 5
- Axios
- TypeScript
- Vite
- Tailwind v4 plus project-specific CSS variables and page styles

## High-Level Structure

The frontend is organized around five active module areas.

### App shell

Lives primarily under `frontend/src/app`.

Owns:

- bootstrap and providers
- route tree
- global layout frame
- header and sidebar navigation
- page container sizing

Module reference:

- [Frontend App Shell](../modules/frontend-app-shell.md)

### Data layer

Lives under `frontend/src/data`.

Owns:

- Axios client configuration
- DTO contracts
- endpoint wrappers
- TanStack Query hooks
- small UI-facing mappers

Module reference:

- [Frontend Data Layer](../modules/frontend-data-layer.md)

### Auth surface

Lives across `data`, `features/auth`, and auth pages.

Owns:

- client token storage
- auth session reads
- login and signup flows
- auth-aware shell behavior

Module reference:

- [Frontend Auth](../modules/frontend-auth.md)

### Sessions workspace

Lives across `pages/SessionsExplorerPage.tsx`, `pages/SessionWorkspacePage.tsx`, and `features/sessions`.

Owns:

- catalog browsing
- session import flow
- workspace URL state
- replay clock state
- driver, lap, and layout coordination

Module reference:

- [Frontend Sessions Workspace](../modules/frontend-sessions.md)

### Widget system

Lives under `frontend/src/widgets`.

Owns:

- widget definitions
- layout schema
- built-in dashboards
- dashboard rendering
- session telemetry widgets
- replay widgets

Module reference:

- [Frontend Widget System](../modules/frontend-widget-system.md)

## Directory Overview

### `frontend/src/app`

Shell, providers, routing, and layout frame.

### `frontend/src/data`

Transport, contracts, query hooks, and mappers.

### `frontend/src/features`

Feature-level runtime logic that sits between raw data and pages.

Current major feature areas:

- `auth`
- `sessions`

### `frontend/src/pages`

Route-level screens and their screen-specific CSS files.

### `frontend/src/widgets`

Reusable dashboard and telemetry building blocks.

### Currently light or unused folders

- `frontend/src/components`
- `frontend/src/core`
- `frontend/src/layouts`

These are not current architecture centers. Most meaningful work lives in the five modules above.

## Runtime Flow

The runtime starts in `frontend/src/main.tsx`.

Current startup sequence:

1. import global CSS
2. create the React root
3. install shared providers through `AppProviders`
4. mount `RouterProvider`

This makes the app shell and routing system the outer frame for all domain screens.

## Route Model

The route tree is defined in `frontend/src/app/router/routes.tsx`.

### Implemented or active routes

- `/`
- `/sessions`
- `/sessions/:sessionId`
- `/login`
- `/signup`
- `/system/health`

### Intentionally placeholder routes

- `/live`
- `/live/:sessionId`
- `/story-feed`
- `/standings`

These routes are already part of the product structure even when their final surfaces are not implemented yet.

## Current Product Surfaces

## Home

The home page is currently a product hub that:

- introduces major product surfaces
- adapts some shell actions to auth state
- presents the direction of live race, sessions, story feed, and standings

## Sessions explorer

The sessions explorer is the entry point to archive workflows.

It currently supports:

- season selection
- race weekend selection
- session selection
- lookback versus simulation mode choice
- direct import into the workspace
- resume of the last active session workspace

## Session workspace

The session workspace is the most advanced frontend surface today.

It supports:

- URL-driven workspace state
- built-in and user layouts
- lazy telemetry widget mounting
- lookback controls
- replay controls for simulation

## System health

The system health page is a useful operational surface that already demonstrates the frontend's ability to compose several backend module reads into one richer screen.

## Current Backend Integration Pattern

The frontend communicates with the backend through the shared Axios client in `data/api/client.ts`.

Important current integration areas:

- auth session flow
- backend and module health
- session catalog and import
- session detail and entries
- lap and telemetry reads
- session replay ticks
- user layout CRUD

The frontend is intentionally assembled from smaller API resources instead of expecting page-specific mega-payloads.

## Widget-Driven Direction

One of the most important frontend architecture decisions is the widget-and-layout model.

The project now distinguishes between:

- widgets, which are the actual renderable units
- layouts, which are compositions of many widgets

That makes it possible to:

- ship built-in layouts in frontend code
- load user-owned layouts from the backend
- keep layout persistence independent from widget implementation
- reuse live-race-safe widgets in simulation mode only

This is a major part of the long-term frontend direction.

## Design System Direction

The visual system is currently implemented through:

- global CSS variables
- reusable shell primitives like `surface-card` and `ui-pill`
- route-level CSS files
- selective inline utility usage

This is not yet a formal component library, but it already behaves like a lightweight design system.

## Why the Current Frontend Shape Is Reasonable

- The app shell, data layer, sessions flow, and widget system are clearly separated.
- Query hooks keep server-state logic out of route rendering code.
- The session workspace is already composable enough for telemetry growth.
- Built-in and saved layouts share one runtime model.
- Placeholder routes allow information architecture work to continue in parallel with implementation.

## Main Architectural Boundaries

### App shell should own

- providers
- route tree
- persistent shell framing
- navigation chrome
- global visual primitives

### Data layer should own

- HTTP client behavior
- DTO types
- API wrappers
- query keys and invalidation

### Features should own

- domain-specific UI state models
- shared feature hooks
- orchestration that is too rich for raw pages but too UI-specific for the data layer

### Widgets should own

- reusable dashboard units
- layout interpretation
- audience-compatible telemetry and replay rendering

### Pages should own

- route composition
- page-specific orchestration
- page-level empty and error states

## Near-Term Frontend Work

- replace remaining placeholder routes with real live race, story, and standings surfaces
- add a layout builder that emits the same `DashboardConfig` shape already used by the workspace
- expand telemetry and replay widget coverage
- strengthen error and recovery patterns across richer API interactions
- decide whether the current CSS primitives should become a more formal component system
