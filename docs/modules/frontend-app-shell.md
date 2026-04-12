# Frontend App Shell

Back to [Frontend Architecture](../architecture/03-frontend-architecture.md)

## Purpose

The frontend app shell owns the runtime frame around every React screen.

It is responsible for:

- bootstrapping React and the router
- providing shared runtime services such as TanStack Query
- defining the global page frame
- exposing top-level navigation
- supplying the visual foundation used by every route

This module is the frontend equivalent of the backend delivery surface. It does not own business data, but every business surface depends on it.

## Why This Module Matters

Without the app shell, the project would just be a pile of route components. The shell gives the product a stable operating frame:

- one place where providers are installed
- one route tree for the whole SPA
- one layout model for marketing and application surfaces
- one shared visual language

That makes later feature work safer. New pages can focus on their own domain logic instead of rebuilding routing, spacing, header behavior, or provider setup.

## Current File Map

### Entry and providers

- `frontend/src/main.tsx`
- `frontend/src/app/providers/AppProviders.tsx`
- `frontend/src/app/providers/query-client.ts`

### Routing

- `frontend/src/app/router/index.tsx`
- `frontend/src/app/router/routes.tsx`

### Shell layout

- `frontend/src/app/layout/AppLayout.tsx`
- `frontend/src/app/layout/AppHeader.tsx`
- `frontend/src/app/layout/AppSidebar.tsx`
- `frontend/src/app/layout/PageContanier.tsx`

### Global styling

- `frontend/src/styles/global.css`

### Route-level pages currently mounted by the shell

- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/SessionsExplorerPage.tsx`
- `frontend/src/pages/SessionWorkspacePage.tsx`
- `frontend/src/pages/SystemHealthPage.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/pages/SignupPage.tsx`
- `frontend/src/pages/FeaturePlaceholderPage.tsx`

### Present-but-not-yet-used folders

- `frontend/src/components/`
- `frontend/src/core/`
- `frontend/src/layouts/`

Those folders are currently scaffolding space rather than active architectural centers. Most real frontend structure lives in `app`, `data`, `features`, `pages`, and `widgets`.

## Bootstrap Flow

The application boot sequence is intentionally small and easy to trace.

### `main.tsx`

`main.tsx` does three things:

1. mounts React into `#root`
2. installs `AppProviders`
3. hands control to `RouterProvider`

This means provider installation happens before any routed page renders.

### `AppProviders.tsx`

`AppProviders` is currently the place where shared runtime providers are attached.

Today it installs:

- `QueryClientProvider`

It creates the query client once through `useState(() => createQueryClient())` so the client instance is stable across rerenders.

### `query-client.ts`

The query client defaults define the project's baseline server-state behavior:

- queries retry once
- queries do not refetch on window focus
- queries are considered fresh for 15 seconds
- mutations do not retry automatically

That is a practical middle ground for this product:

- it keeps the UI responsive during local development
- it avoids noisy refetch behavior while working across dense dashboard screens
- it keeps retry behavior conservative for mutation flows like session import or layout save

## Routing Responsibilities

The route tree lives in `frontend/src/app/router/routes.tsx`.

## Current Route Surface

- `/`
- `/sessions`
- `/sessions/:sessionId`
- `/live`
- `/live/:sessionId`
- `/story-feed`
- `/standings`
- `/compare/:sessionId`
- `/login`
- `/signup`
- `/home`
- `/system/health`

## Route Design Notes

### `AppLayout` wraps the full route tree

The shell uses one shared layout for the product, then changes how much framing is visible depending on the current route.

### Marketing-style routes

`/`, `/login`, and `/signup` are treated as marketing or account-entry surfaces.

For those routes:

- the sidebar is hidden
- the page uses a simpler centered frame

### Application routes

All other routes render inside the operational shell:

- sticky header
- left navigation rail
- routed page content area

### Placeholder routes are intentional

`/live`, `/live/:sessionId`, `/story-feed`, and `/standings` still use `FeaturePlaceholderPage`.

That is not accidental dead code. It allows the product information architecture and navigation model to exist before every surface is fully implemented.

## Shell Layout Responsibilities

## `AppLayout.tsx`

`AppLayout` is the top-level composition component.

It decides:

- whether the current route should be treated as a marketing surface
- whether to render the sidebar
- how wide the central page frame should be

It also keeps the header mounted across the entire app so navigation and auth actions feel continuous.

## `AppHeader.tsx`

The header owns:

- top navigation pills
- product identity
- auth session awareness
- sign-in, sign-up, diagnostics, and sign-out actions

Important behavior:

- it calls `useAuthSession()` to reflect backend auth state
- sign-out is frontend-local for now, because the token is removed from `localStorage`
- after logout it updates and invalidates the `["auth-session"]` query cache, then navigates to `/login`

This makes the header the frontend's primary auth-aware shell component.

## `AppSidebar.tsx`

The sidebar is a compact navigation rail for application routes.

Its current behavior is notable:

- desktop-only
- narrow by default
- expands on hover or focus
- shows compact status dots first and fuller badges when expanded

This makes it useful without permanently consuming too much horizontal space, which matters a lot for telemetry-heavy surfaces like the sessions workspace.

## `PageContanier.tsx`

`PageContanier.tsx` is a lightweight width-and-padding wrapper used by route pages.

It supports:

- `default`
- `wide`
- `full`

This small abstraction matters because the product already has pages with very different density needs:

- normal content pages
- wide telemetry workspaces
- potential future full-width command surfaces

Note: the file name is currently spelled `PageContanier.tsx`. The codebase consistently imports that path, so the spelling is stable even if it is not ideal.

## Styling System

The global styling contract is defined in `frontend/src/styles/global.css`.

## What the global stylesheet owns

- imported fonts
- Tailwind v4 inclusion through `@import "tailwindcss"`
- CSS custom properties for color, typography, motion, and elevation
- shared primitives like `.surface-card`, `.button-primary`, `.button-secondary`, and `.ui-pill`
- page-wide background treatment
- global typography and selection behavior

## Current visual primitives

The product already relies on a small number of reusable primitives:

- `surface-card` for elevated panels
- `button-primary` for strong red actions
- `button-secondary` for neutral shell actions
- `ui-pill` and tone variants for small state tags
- `display-font` for motorsport-style headings

This is the real frontend design system right now, even though it is still implemented as CSS primitives rather than a dedicated component library.

## How route styling currently works

The app uses a hybrid model:

- shared primitives and tokens in `global.css`
- page-local CSS files for large screen-specific layouts
- utility classes inline for simple layout composition

Examples:

- `home-page.css`
- `sessions-page.css`
- `system-health-page.css`
- `dashboard-renderer.css`

That split is healthy for the current size of the project. It keeps cross-app styling centralized while allowing dense route pages to have their own layout logic.

## Boundaries

### Belongs here

- app bootstrap
- provider installation
- route registration
- persistent header and sidebar framing
- page-width wrappers
- global tokens and shared visual primitives

### Does not belong here

- endpoint-specific API logic
- session-domain data orchestration
- auth request shapes
- widget registry rules
- telemetry chart logic

Those concerns belong in `data`, `features`, or `widgets`.

## Current Strengths

- Small startup path that is easy to reason about
- Clear separation between route shell and feature code
- Compact navigation model that already supports future surfaces
- Shared design primitives that make the UI feel coherent

## Current Limitations

- No route-level error boundary strategy yet
- No suspense or streaming strategy
- No dedicated design-system component package
- Some route pages still depend on placeholders
- The currently empty `components`, `core`, and `layouts` folders can be confusing until they are either used or removed

## Future Work

- add route-level error boundaries and recovery states
- introduce stronger shell-level loading patterns if the route tree gets denser
- decide whether the visual primitives should graduate into shared React components
- consolidate naming around `PageContanier` if a cleanup pass is scheduled
- document mobile shell behavior in more depth once live race surfaces are implemented
