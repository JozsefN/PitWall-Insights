# Database and Migrations

Back to [Backend Architecture](./02-backend-architecture.md)

Related module docs:

- [Session Domain](../modules/session-domain.md)
- [Identity Auth](../modules/identity-auth.md)
- [Ingestion](../modules/ingestion.md)
- [Normalization](../modules/normalization.md)

## Purpose

The database stores:

- selected imported sessions
- normalized session structure
- user/auth data
- module-level operational state such as ingestion history

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
- future derived metrics

Examples:

- raw FastF1 car channels belong in telemetry tables
- lap timing and tyre data belong in canonical session tables
- future values such as acceleration, distance-driven, driver-ahead, or specialized chart series should eventually live in [Feature Metrics](../modules/feature-metrics.md) unless the team explicitly decides to treat them as canonical

## Migrations

Alembic tracks schema evolution in `backend/migrations/versions`.

Each migration contains:

- `upgrade()` to apply schema changes
- `downgrade()` to roll them back

The migration history currently includes:

- initial session table
- users table
- expanded entry-centric session cache schema

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
- better pagination/downsampling support for telemetry-heavy reads
- partitioning or retention strategies if telemetry volume grows significantly
- optional job tracking if imports become asynchronous
