# Backend Architecture

Back to [System Architecture](./01-system-architecture.md)

## Top-Level Layout

The backend lives under `backend/` and is organized into three main areas:

- `app/`
- `modules/`
- `migrations/`

### `app/`

Application bootstrap and configuration:

- `main.py` creates the ASGI app entrypoint
- `bootstrap.py` configures FastAPI, CORS, and router registration
- `config.py` reads environment-driven settings

### `modules/`

Business and delivery logic grouped by feature/module:

- [Session Domain](../modules/session-domain.md)
- [Identity Auth](../modules/identity-auth.md)
- [Ingestion](../modules/ingestion.md)
- [Normalization](../modules/normalization.md)
- [Feature Metrics](../modules/feature-metrics.md)
- [Story Feed](../modules/story-feed.md)
- `delivery_api`
- `storage`

### `migrations/`

Alembic configuration and schema migration history.

## Cross-Cutting Backend Layers

### Delivery Layer

Located in `modules/delivery_api/api`.

Responsibilities:

- declare HTTP routes
- validate request/query payloads
- build application services
- translate domain/service errors into HTTP responses

The main API router includes:

- health routes
- auth routes
- session routes
- module health routes for ingestion, normalization, feature metrics, and story feed

### Application Layer

Usually located in `modules/<module>/application`.

Responsibilities:

- orchestrate use cases
- coordinate repositories and adapters
- keep route handlers thin

Examples:

- `SessionService`
- `AuthService`
- `IngestionService`
- `NormalizationService`

### Domain and Contract Layer

Usually located in `modules/<module>/domain`.

Responsibilities:

- define Pydantic response/request models or domain-facing contract objects
- keep naming stable for the rest of the application

### Infrastructure Layer

Usually located in `modules/<module>/infrastructure`.

Responsibilities:

- SQLAlchemy models
- repositories
- external adapters
- low-level persistence concerns

## Session Import Architecture

The session import flow is intentionally split across modules:

1. `delivery_api` exposes the import route
2. `session_domain` application service coordinates the use case
3. `ingestion` pulls source data from FastF1
4. `normalization` converts source data into a canonical snapshot
5. `session_domain` repository persists the snapshot into PostgreSQL

This keeps source-specific logic out of the repository and keeps the repository free of FastF1-specific assumptions.

## Storage Infrastructure

The shared storage layer lives in `modules/storage/infrastructure`.

It contains:

- the SQLAlchemy declarative base
- the engine and session factory
- the database health check
- the `get_db` dependency used by FastAPI routes

## Current Backend Module Status

### Fully active

- `identity_auth`
- `session_domain`
- `ingestion`
- `normalization`
- `delivery_api`
- `storage`

### Present but still mostly placeholders

- `feature_metrics`
- `story_feed`

These two already have module health routes, but they do not yet own substantial production logic.

## Conventions Used In The Codebase

- FastAPI routes return plain JSON-compatible objects or Pydantic models
- SQLAlchemy 2-style declarative models are used for persistence
- Repositories handle direct database interaction
- Application services coordinate cross-module work
- Environment configuration is centralized in `app/config.py`

## Why This Structure Works Well Here

- It is easy to discover where a change belongs.
- It keeps the session model readable even as the schema grows.
- It allows future metrics and replay logic to be added without reworking the ingestion pipeline.
- It matches the current scale of the project without over-engineering the service boundaries.

## Related Docs

- [API Design](./05-api-design.md)
- [Data Flow](./04-data-flow.md)
- [Database and Migrations](./06-database-and-migrations.md)
