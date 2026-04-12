# Ingestion

Back to [Backend Architecture](../architecture/02-backend-architecture.md)

## Purpose

The ingestion module owns communication with external session data sources.

Today that means:

- FastF1 is the only active source

The goal of ingestion is to load source data and convert it into plain source-facing structures that the normalization module can understand.

## Current Responsibilities

- report ingestion module health and FastF1 readiness
- list a season/session catalog through FastF1
- load one selected session from FastF1
- convert FastF1 objects into plain record collections

## Current Main Components

### `IngestionService`

Application-level facade used by the session domain.

### `IngestionSourceAdapter`

Thin coordination wrapper around the real source adapter.

### `FastF1Adapter`

The real source implementation for v1.

It is responsible for:

- enabling FastF1 local cache
- loading season schedule data
- loading one selected session
- extracting source records for:
  - drivers/results
  - laps
  - weather
  - session status
  - track status
  - race control messages
  - car telemetry
  - position telemetry

## What Ingestion Should Not Do

The ingestion module should not:

- write directly to canonical session tables
- decide long-term relational structure
- own derived metrics

Those responsibilities belong to normalization and session-domain persistence.

## Storage Relationship

The ingestion module is related to:

- `ingestion_runs` for import tracking

At the moment it does not persist raw files or raw payload archives. If the project later needs reproducibility at the source-payload level, this module is the right place to introduce raw-payload storage or file references.

## Design Notes

- Source-specific assumptions should stay here.
- If additional providers are added later, they should plug in beside FastF1 rather than leaking provider logic into the rest of the backend.
- Imported telemetry should stay as close as possible to the source when first extracted.

## Future Work

- support additional sources if needed
- introduce better import error classification
- add optional asynchronous import execution
- optionally store raw payload references for reprocessing/debugging
