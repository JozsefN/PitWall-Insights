# Frontend Auth

Back to [Frontend Architecture](../architecture/03-frontend-architecture.md)

## Purpose

The frontend auth module owns how the client understands and reacts to authentication state.

It is responsible for:

- sign-in and sign-up UI
- auth token storage on the client
- auth session lookups
- header-level authenticated shell behavior
- enabling authenticated-only features such as saved layouts

It is intentionally small. The backend owns real credential validation and token creation. The frontend owns session awareness and client-side flow.

## Why This Module Matters

Even though authentication is currently lightweight, it already affects several important product behaviors:

- whether the shell shows account or guest actions
- whether `/api/layouts` should be queried
- whether user-owned layouts can appear beside built-ins
- whether session resume flows feel personal and continuous

That means auth is already more than just a login form. It is the feature gate for user-specific workspace behavior.

## Current File Map

### API and contracts

- `frontend/src/data/api/auth.api.ts`
- `frontend/src/data/contracts/auth.contracts.ts`
- `frontend/src/data/queries/auth.queries.ts`

### Feature hook

- `frontend/src/features/auth/useAuthSession.ts`

### Route pages

- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/pages/SignupPage.tsx`

### Shell integrations

- `frontend/src/app/layout/AppHeader.tsx`
- `frontend/src/data/api/client.ts`

## Current Auth Model

The current model is stateless and token-based.

### Backend responsibilities

The backend:

- validates credentials
- returns bearer tokens
- decodes tokens in `/api/auth/session`

### Frontend responsibilities

The frontend:

- stores the token in `localStorage`
- adds the token to the `Authorization` header through the shared Axios interceptor
- asks the backend whether the session is authenticated
- updates shell UI based on that response

This is a deliberately pragmatic setup for a product still early in its UI growth.

## Token Storage Strategy

The client stores the token under:

- `localStorage["auth_token"]`

This token is read centrally by the Axios request interceptor in `data/api/client.ts`.

## Why the storage strategy is simple

The current auth model is optimized for:

- ease of local development
- clarity of frontend behavior
- minimal moving parts

It does not currently aim to solve:

- refresh token rotation
- server-driven session revocation
- complex multi-device session management

## Auth Query Surface

## `auth.api.ts`

The auth API file exposes:

- `getAuthHealth()`
- `getAuthSession()`
- `signup(payload)`
- `login(payload)`
- `logout()`

`logout()` is intentionally just a local token removal step right now.

## `auth.queries.ts`

This file exposes TanStack Query wrappers for auth-related reads.

That keeps auth health and auth session state consistent with the rest of the app's server-state strategy.

## `useAuthSession.ts`

`useAuthSession()` is the main feature-level auth hook.

It:

- uses `getAuthSession`
- stores the result under the `["auth-session"]` query key
- keeps auth-session data fresh for 60 seconds

This hook is used by shell components rather than forcing each page to manually read session state.

## Current UI Flow

## Login and signup pages

The route pages handle:

- collecting credentials
- calling the relevant mutation path
- persisting the returned token
- navigating into the product after success

Those pages are entry surfaces, not deep business modules. The real long-lived auth behavior happens after the token is stored.

## Header integration

`AppHeader.tsx` is the main auth-aware shell component.

It uses `useAuthSession()` to decide whether to show:

- guest actions: sign in and sign up
- authenticated actions: email, diagnostics, and sign out

On logout it:

1. clears the token
2. updates the `["auth-session"]` cache to an unauthenticated value
3. invalidates the auth-session query
4. navigates to `/login`

That means logout feels immediate even before the next server round trip completes.

## Sessions and Layouts Impact

Auth is especially relevant to the sessions workspace.

### Built-in vs saved layouts

Built-in layouts are always available.

Saved layouts are only fetched when `useAuthSession()` reports an authenticated user. This is why `useLayoutsQuery()` is conditionally enabled from the workspace page.

### Resume behavior

The session workspace resume feature is currently stored locally, not server-side. That means it is available independent of authentication, but authenticated users can combine it with their own saved layouts.

## Boundaries

### Belongs here

- token storage behavior
- auth session reads
- login and signup request flow
- shell-level auth awareness
- frontend gating of user-specific API reads

### Does not belong here

- password hashing
- token signing
- user persistence
- backend authorization rules
- layout CRUD implementation

Those belong to backend modules such as `identity_auth` and the backend layout persistence surface.

## Current Strengths

- Very easy to reason about
- Small enough to debug quickly
- Already good enough for authenticated layout ownership and shell state
- Cleanly centralized through the shared Axios client and auth-session hook

## Current Limitations

- No refresh token flow
- No server-side logout or revocation mechanism
- No route-guard abstraction yet
- No role or permission model
- Token persistence uses `localStorage`, which is simple but intentionally basic

## Future Work

- add route guards if more authenticated-only surfaces appear
- introduce refresh behavior if the token lifetime requires it
- expand user-session UX beyond basic sign-in and sign-out
- document auth error states more explicitly in the login and signup pages
