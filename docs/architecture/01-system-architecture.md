# System Architecture

Back to [Overview](./00-overview.md)

## High-Level Pipeline

External source -> [Ingestion](../modules/ingestion.md) -> [Normalization](../modules/normalization.md) -> PostgreSQL session cache -> [Feature Metrics](../modules/feature-metrics.md) -> [Decision Engine](../modules/decision-engine.md) -> [Delivery API](./05-api-design.md) -> Frontend

## Primary External Dependency

The active v1 source is FastF1.

FastF1 provides:

- season schedule and event/session discovery
- lap timing data
- car telemetry and position telemetry
- weather samples
- session status, track status, and race control data

The system currently treats FastF1 as the import source of truth and stores a normalized representation internally.

## Main Runtime Components

### Frontend

- React application in `frontend/`
- route-driven screens for archive, live, story-feed, standings, and auth
- React Query for data fetching and caching
- Axios client for backend communication

### Delivery API

- FastAPI application in `backend/app` and `backend/modules/delivery_api`
- central HTTP layer for health, auth, session cache, and module health routes
- converts backend service results into JSON responses

### Domain Modules

- `session_domain` owns the core session cache and read/query model
- `identity_auth` owns user signup/login/session inspection
- `ingestion` owns external source access
- `normalization` owns canonical transformation into the internal schema
- `feature_metrics` owns derived analysis metrics and metric insight surfaces
- `decision_engine` owns rule-based signal selection from metric outputs
- `story_feed` is reserved for season/news/history content

### Storage

- PostgreSQL is the persistent backing store
- SQLAlchemy models define the schema
- Alembic tracks schema evolution

## Architectural Style

The backend follows a light layered structure:

1. delivery routes receive HTTP requests
2. application services coordinate use cases
3. repositories persist and query relational data
4. infrastructure adapters talk to external systems or the database

This is intentionally simpler than a heavy DDD or CQRS stack, but the boundaries are still explicit enough to scale.

## Important Architectural Decisions

### Selected-session cache

The database is not yet a full archive of all F1 sessions. Sessions are imported on demand and stored with expiry metadata.

### Entry-centric model

The driver/car combination inside one session is modeled as `session_entries`. This lets all driver-specific information connect to one root entity without creating a separate table per driver.

### Raw vs derived data

- Raw FastF1 channels should stay in the canonical session cache.
- Derived values such as pace rating, consistency, distance-driven, driver-ahead, or tyre indicators should live in feature metrics unless there is a strong reason to treat them as canonical.
- Rule-selected highlights such as strongest pace driver or recent improver should live in the decision engine and be exposed through feature-metric insight APIs.

### Replay readiness

The backend creates `session_ticks` so future consumers can answer both:

- what comes next for a specific entry
- what happened across the whole session at one aligned moment

## Related Docs

- [Backend Architecture](./02-backend-architecture.md)
- [Data Flow](./04-data-flow.md)
- [Database and Migrations](./06-database-and-migrations.md)
