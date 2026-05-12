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
- honor the selected import profile when deciding whether to request telemetry

## Current Main Components

### `IngestionService`

Application-level facade used by the session domain.

It depends on `SessionSourcePort`, so the application layer does not know which
provider implementation is active.

### `SessionSourcePort`

Application-layer protocol for session data providers.

Provider implementations must support:

- reporting source health/status
- listing a season catalog
- loading one selected session bundle

### Provider Registry

`provider_registry.py` selects the active provider from `settings.ingestion_source`.

The only registered provider today is `fastf1`.

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

For `core` imports, FastF1 is called with telemetry disabled and the telemetry
collections stay empty. For `full` imports, FastF1 telemetry is loaded and
extracted.

## Provider Cache Policy

FastF1's own cache is treated as provider scratch storage, not application
state.

By default, the cache is resolved outside the repository under the operating
system's user cache directory:

- Windows: `%LOCALAPPDATA%/pitwall-insights/fastf1`
- macOS: `~/Library/Caches/pitwall-insights/fastf1`
- Linux: `$XDG_CACHE_HOME/pitwall-insights/fastf1` or `~/.cache/pitwall-insights/fastf1`

`FASTF1_CACHE_DIR` can still override this. Absolute paths are used directly.
Relative paths are resolved under the PitWall app cache root, not under the
current working directory.

This keeps FastF1 pickle and HTTP cache files disposable and out of source
control. The durable application cache is the PostgreSQL-backed canonical
session cache owned by `session_domain`.

If the project later needs reproducible raw imports, ingestion should add an
app-owned raw artifact store using stable file formats such as Parquet or JSONL
plus database metadata. FastF1 `.ff1pkl` files should not become the durable
application contract.

## What Ingestion Should Not Do

The ingestion module should not:

- write directly to canonical session tables
- decide long-term relational structure
- own derived metrics

Those responsibilities belong to normalization and session-domain persistence.

## Storage Relationship

The ingestion module is related to:

- `ingestion_runs` for import tracking
- `import_jobs` indirectly through the session-import worker

At the moment it does not persist raw files or raw payload archives. If the project later needs reproducibility at the source-payload level, this module is the right place to introduce raw-payload storage or file references.

## Design Notes

- Source-specific assumptions should stay here.
- If additional providers are added later, they should plug in beside FastF1 rather than leaking provider logic into the rest of the backend.
- Imported telemetry should stay as close as possible to the source when first extracted.

## Future Work

- support additional sources if needed
- introduce better import error classification
- keep source loading profile-aware as more providers are added
- optionally store raw payload references for reprocessing/debugging
