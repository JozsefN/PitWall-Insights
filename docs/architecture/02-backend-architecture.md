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
- [Session Import](../modules/session-import.md)
- [Identity Auth](../modules/identity-auth.md)
- [Ingestion](../modules/ingestion.md)
- [Normalization](../modules/normalization.md)
- [Feature Metrics](../modules/feature-metrics.md)
- [Decision Engine](../modules/decision-engine.md)
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
- session import job routes
- module health routes for ingestion, normalization, feature metrics, decision engine, and story feed
- metric score, metric insight, and decision-signal routes

### Application Layer

Usually located in `modules/<module>/application`.

Responsibilities:

- orchestrate use cases
- coordinate repositories and adapters
- keep route handlers thin

Examples:

- `SessionService`
- `ImportJobService`
- `AuthService`
- `IngestionService`
- `NormalizationService`
- `FeatureMetricsService`
- `DecisionEngineService`

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

1. `delivery_api` exposes synchronous import and import-job routes.
2. `session_import` owns queued jobs, worker progress, retries, and cleanup.
3. `session_domain` owns canonical session persistence and reads.
4. `ingestion` pulls source data from FastF1 through a provider port.
5. `normalization` converts source data into a canonical snapshot.
6. `session_domain` repository persists the snapshot into PostgreSQL.

This keeps source-specific logic out of the repository and keeps the repository free of FastF1-specific assumptions.

The current strategic choice is to keep telemetry in PostgreSQL and measure
real import/read pain before adding an artifact store. Import profiles and
background jobs solve the immediate slowness/observability problem with less
architecture weight.

## Storage Infrastructure

The shared storage layer lives in `modules/storage/infrastructure`.

It contains:

- the SQLAlchemy declarative base
- the engine and session factory
- the database health check
- the `get_db` dependency used by FastAPI routes

## Provider Scratch Storage

External-provider caches are separate from application storage.

FastF1 uses a local scratch cache for HTTP responses and parsed provider data.
The backend resolves this outside the repository by default and treats it as
disposable. PostgreSQL remains the application-owned cache for imported
canonical sessions.

## Current Backend Module Status

### Fully active

- `identity_auth`
- `session_domain`
- `session_import`
- `ingestion`
- `normalization`
- `feature_metrics`
- `decision_engine`
- `delivery_api`
- `storage`

### Present but planned

- `story_feed`

`story_feed` currently reports planned season/news/history surfaces. It is not the home for current-session metric insight cards.

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
- It lets metric formulas, rule-selected insights, and future editorial story content evolve independently.
- It matches the current scale of the project without over-engineering the service boundaries.

## Related Docs

- [API Design](./05-api-design.md)
- [Data Flow](./04-data-flow.md)
- [Database and Migrations](./06-database-and-migrations.md)
