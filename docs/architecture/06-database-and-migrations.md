# Database and Migrations

Back to [Backend Architecture](./02-backend-architecture.md)

Related module docs:

- [Session Domain](../modules/session-domain.md)
- [Session Import](../modules/session-import.md)
- [Telemetry Materialization](../modules/telemetry-materialization.md)
- [Identity Auth](../modules/identity-auth.md)
- [Ingestion](../modules/ingestion.md)
- [Normalization](../modules/normalization.md)
- [Feature Metrics](../modules/feature-metrics.md)
- [Decision Engine](../modules/decision-engine.md)

## Purpose

The database stores:

- selected imported sessions
- normalized session structure
- user/auth data
- module-level operational state such as import jobs and ingestion history

The current design is not a generic warehouse. It is a relational, entry-centric cache of selected sessions with enough structure to support archive views and future replay/metric work.

## Stack

- PostgreSQL
- SQLAlchemy 2 declarative models
- Alembic migrations

## Shared Database Infrastructure

Shared infrastructure lives in `backend/modules/storage/infrastructure`.

Important pieces:

- `base.py` defines the shared declarative base
- `db.py` creates the engine and session factory
- `get_db()` provides a FastAPI dependency for repositories and services

## Current Schema Groups

### Auth tables

- `users`

Owned by: [Identity Auth](../modules/identity-auth.md)

### Session reference tables

- `seasons`
- `event_weekends`
- `event_sessions`
- `drivers`
- `teams`
- `session_entries`

Owned by: [Session Domain](../modules/session-domain.md)

These tables define the stable relational backbone of a cached session.

`event_sessions` also records the import profile:

- `import_profile`: `core` or `full`
- `telemetry_status`: `not_loaded`, `loaded`, `partial`, or `unavailable`
- `pinned_at`: future lifecycle override for sessions that should not expire
- `deleted_at`: reserved lifecycle marker for future soft-delete behavior

### Entry detail tables

- `entry_results`
- `entry_laps`
- `entry_stints`

These tables hold race/session detail attached to one `session_entry`.

### Session-level event tables

- `ingestion_runs`
- `session_weather_samples`
- `session_status_events`
- `session_track_status_events`
- `session_race_control_messages`
- `session_ticks`

These tables describe what happened across the session as a whole.

`ingestion_runs` stores generic source metadata in application code. The
database column for source version is still named `fastf1_version` until a later
migration renames it to `source_version`.

### Import job tables

- `import_jobs`

Owned by: [Session Import](../modules/session-import.md)

This table tracks queued/running/completed/failed import requests, their import
profile, heartbeat, retry count, final `session_id`, `source_version`, and row
count. It is operational state, not canonical motorsport data.

### Telemetry materialization tables

- `telemetry_cache_segments`
- `telemetry_materialization_jobs`

Owned by: [Telemetry Materialization](../modules/telemetry-materialization.md)

These tables track on-demand telemetry slices. A slice is keyed by session,
entry, telemetry kind, scope, and optional lap. The cached sample rows still live
in the canonical telemetry tables.

### Telemetry tables

- `car_telemetry_samples`
- `position_samples`

These hold raw per-entry telemetry and position series, connected to:

- the owning `session_entry`
- the aligned `session_tick`
- optional `entry_lap`
- optional `entry_stint`

## Important Relationships

The most important relationship chain is:

`season`
-> `event_weekend`
-> `event_session`
-> `session_entry`
-> `entry_lap` / `entry_stint` / telemetry samples

Important design consequences:

- every telemetry sample belongs to one session entry
- every telemetry sample can align to one session-wide tick
- driver and team identity are resolved through linked reference tables instead of repeated on every row

## Replay-Oriented Storage

`session_ticks` are a key part of the schema.

They provide a session-wide time axis that can align:

- telemetry samples
- lap boundaries
- weather changes
- status changes
- race control events

This is what allows future replay and multi-entry comparisons to be built on top of the current relational schema.

## Raw vs Derived Data

The current database design deliberately separates:

- canonical imported session data
- on-demand derived metrics

Examples:

- raw FastF1 car channels belong in telemetry tables
- lap timing and tyre data belong in canonical session tables
- current values such as pace rating, consistency score, and recent lap trend live in [Feature Metrics](../modules/feature-metrics.md)
- rule-selected highlights such as pace leader or recent improver live in [Decision Engine](../modules/decision-engine.md)
- future values such as acceleration, distance-driven, driver-ahead, tyre health, or specialized chart series should also live in feature metrics unless the team explicitly decides to treat them as canonical

There are no feature-metric result tables yet. The current metrics compute on
demand from `session_entries` and `entry_laps`, which means this feature did not
need a migration. Future persisted metric tables should store metric id,
version, scope, window, config version, confidence, components, corrections, and
input coverage so old calculations remain explainable.

The story-feed module also has no tables yet. It is currently a planned
season/news/history surface, not storage for current-session metric insights.

## Migrations

Alembic tracks schema evolution in `backend/migrations/versions`.

Each migration contains:

- `upgrade()` to apply schema changes
- `downgrade()` to roll them back

The migration history currently includes:

- initial session table
- users table
- expanded entry-centric session cache schema
- user dashboard layouts
- import jobs, import profiles, and session lifecycle columns
- telemetry materialization jobs and cache segment metadata

## Standard Workflow

1. Change the SQLAlchemy models.
2. Generate or write the Alembic migration.
3. Review the migration carefully.
4. Apply with `alembic upgrade head`.
5. Test against a real database before assuming the schema is correct.

## Practical Rules

- Never manually patch production schema outside migrations.
- Review foreign keys and indexes, not just columns.
- Be careful with destructive migration steps when replacing placeholder tables.
- Keep table naming consistent with module ownership and query usage.

## Future Database Work

Likely future additions:

- feature-metric tables for derived telemetry series
- decision-rule/config tables if thresholds need operator tuning
- story-feed source/item tables after the season-news content strategy is defined
- better pagination/downsampling support for telemetry-heavy reads
- partitioning or retention strategies if telemetry volume grows significantly
- artifact storage only if PostgreSQL telemetry volume or raw replay needs prove it necessary
