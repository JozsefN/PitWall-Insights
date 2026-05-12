# Normalization

Back to [Backend Architecture](../architecture/02-backend-architecture.md)

## Purpose

The normalization module converts source-shaped session data into the backend's canonical session snapshot.

Its job is not just field renaming. It is where the backend decides:

- what the internal session model looks like
- how session entries are identified
- how laps and stints are shaped
- whether the session snapshot represents a `core` or `full` import
- how telemetry attaches to entries and aligns to session ticks

## Current Responsibilities

- expose normalization health/readiness
- build a `SessionSnapshot` from a source session bundle
- create canonical payloads for:
  - season
  - weekend
  - session
  - drivers
  - teams
  - entries
  - results
  - laps
  - stints
  - weather/status/control events
  - ticks
  - car telemetry samples
  - position samples

## Source-Specific Snapshot Builders

The current normalization logic lives in `FastF1SessionSnapshotBuilder`.
`NormalizationService` selects a builder from the source on the incoming
`SourceSessionBundle`.

Important behaviors:

- participants are resolved from drivers, results, laps, and telemetry sources
- a source-facing row set becomes a normalized `session_entry`
- laps are repaired when start/end timing needs fallback handling
- stints are derived from lap/stint information
- telemetry samples are assigned to lap and stint when possible
- `session_ticks` are built from the union of observed session timestamps
- `event_sessions.telemetry_status` is set from the import profile

For `core` imports, telemetry row sets are empty and the builder still produces
the canonical session/lap/event structure. For `full` imports, the same builder
adds car and position telemetry payloads.

## Why This Module Exists Separately

Without normalization, the repository would need to understand FastF1-specific shapes and rules.

Separating normalization gives several benefits:

- source-specific logic stays out of persistence
- future new sources can normalize into the same snapshot contract
- canonical session decisions are made in one place

## Canonical vs Derived

Normalization should produce:

- canonical session facts
- canonical structure
- canonical linkages between tables

Normalization should not become a dumping ground for every fancy metric. If a value is meaningfully derived for analysis rather than needed for the canonical session model, it should usually live in feature metrics.

## Database Relationship

Normalization itself does not own tables directly. Instead, it produces the canonical payload written by the session-domain repository into:

- session structure tables
- entry detail tables
- session event tables
- telemetry tables

See [Database and Migrations](../architecture/06-database-and-migrations.md).

## Future Work

- support multiple source adapters through one canonical snapshot contract
- tighten edge-case handling for atypical sessions
- extend canonical coverage when more raw source fields become important
- hand off derived analytics to feature metrics rather than expanding canonical scope indefinitely
