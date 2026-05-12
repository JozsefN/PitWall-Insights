# Session Domain

Back to [Backend Architecture](../architecture/02-backend-architecture.md)

## Purpose

The session domain owns the core motorsport session model inside the backend.

It is responsible for:

- representing imported sessions in a stable internal shape
- storing session structure in PostgreSQL
- exposing read/query operations for archive-style frontend use
- acting as the boundary between normalization output and delivery API reads
- storing whether a cached session has `core` or `full` data

## Why This Module Is Central

The product is currently session-centric. A user is expected to:

- browse a season/session catalog
- import or open a session
- inspect entries, laps, telemetry, and later metrics

Because of that, this module is the backbone of the backend.

## Core Domain Model

The most important concept is `session_entries`.

One `session_entry` represents one driver/car/team combination in one session.

That entry becomes the root for:

- classified result
- laps
- stints
- car telemetry samples
- position samples

This avoids the need for a separate physical table per driver while still keeping all driver-specific data strongly connected.

## Main Persistence Groups

### Reference and session structure

- `seasons`
- `event_weekends`
- `event_sessions`
- `drivers`
- `teams`
- `session_entries`

### Entry detail

- `entry_results`
- `entry_laps`
- `entry_stints`

### Session event context

- `session_ticks`
- `session_weather_samples`
- `session_status_events`
- `session_track_status_events`
- `session_race_control_messages`

### Entry-owned telemetry

- `car_telemetry_samples`
- `position_samples`

## Application Responsibilities

The session-domain application service currently coordinates:

- catalog reads from ingestion
- selected-session import
- session list/detail reads
- entry list reads
- lap reads
- telemetry reads
- tick reads

This module is therefore both:

- the owner of the canonical cached session shape
- the main orchestration layer for archive session access

## Repository Responsibilities

The repository handles:

- writing a normalized snapshot transactionally
- upserting shared reference entities
- deleting expired sessions when called by the import worker
- deleting removed sessions
- reading session summaries and session details
- reading entry-scoped laps and telemetry
- reading replay-alignment ticks

The repository should not contain FastF1-specific parsing logic. By the time data reaches the repository, it should already be in the normalization module's canonical snapshot format.

## Public API Surface

The session domain is exposed through:

- `GET /api/sessions/catalog`
- `POST /api/sessions/import`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}`
- `DELETE /api/sessions/{session_id}`
- `GET /api/sessions/{session_id}/entries`
- `GET /api/sessions/{session_id}/entries/{entry_id}/laps`
- `GET /api/sessions/{session_id}/entries/{entry_id}/telemetry/car`
- `GET /api/sessions/{session_id}/entries/{entry_id}/telemetry/position`
- `GET /api/sessions/{session_id}/ticks`

## Boundaries

### Belongs here

- canonical session structure
- selected-session cache lifecycle
- entry/lap/stint/telemetry persistence
- session-oriented read models
- `event_sessions.import_profile` and `event_sessions.telemetry_status`

### Does not belong here

- direct FastF1 ingestion details
- source-specific cleanup/parsing rules
- import job queue state and worker heartbeats
- advanced derived metrics like acceleration or driver-ahead analytics
- editorial/story logic

Those concerns belong in ingestion, normalization, session_import,
feature_metrics, or story_feed.

Import job queue state belongs in [Session Import](./session-import.md).

## Future Work

Likely future extensions for this module:

- richer session detail projections
- pagination/filtering/downsampling controls for telemetry reads
- better replay-oriented query helpers
- tighter frontend contracts for widgets and chart consumers
