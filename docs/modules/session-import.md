# Session Import

Back to [Backend Architecture](../architecture/02-backend-architecture.md)

## Purpose

The session import module owns asynchronous import orchestration.

It does not own FastF1 parsing, canonical session tables, or telemetry storage.
Its job is to make imports observable and worker-driven so the API process does
not have to sit on a slow FastF1 load.

## Why This Exists

FastF1 session loading can be slow, especially when full telemetry is requested.
The first architecture temptation was a full artifact system, but that would add
raw-file lifecycle, object storage, replay manifests, and reprocessing contracts
before the project has proven that PostgreSQL telemetry is the bottleneck.

The chosen design is intentionally lean:

1. Add import profiles.
2. Add import jobs.
3. Add a worker.
4. Keep normalized telemetry in PostgreSQL.
5. Materialize telemetry on demand by selected session segment.
6. Measure import and read pain using job/run metadata.
7. Add artifacts only if telemetry volume or reproducibility requires it.

## Import Profiles

Import profiles control how much source data ingestion asks for.

### `core`

`core` is the default profile.

It loads the session structure needed to open a session quickly:

- event/session metadata
- drivers and teams
- results
- laps
- stints derived from laps
- weather
- session status
- track status
- race control messages
- session ticks derived from the available timeline data

It does not load FastF1 car telemetry or position telemetry.

Persisted sessions imported with this profile use:

- `event_sessions.import_profile = "core"`
- `event_sessions.telemetry_status = "not_loaded"`

### `full`

`full` loads everything in `core` plus:

- car telemetry samples
- position samples

Persisted sessions imported with this profile use:

- `event_sessions.import_profile = "full"`
- `event_sessions.telemetry_status = "loaded"` when both telemetry streams load
- `event_sessions.telemetry_status = "partial"` when only one telemetry stream loads
- `event_sessions.telemetry_status = "unavailable"` when FastF1 cannot provide telemetry

If a `full` import is requested for a session already cached as `core`, the
repository refreshes the cached session so telemetry is actually written.

## Job Lifecycle

Import jobs are stored in `import_jobs`.

Supported statuses:

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`

Supported progress stages:

- `queued`
- `loading_source`
- `normalizing`
- `persisting`
- `completed`
- `failed`

The job row is the operational record for the import request. The canonical
session rows are still owned by `session_domain`.

## Worker Workflow

The worker entrypoint is `backend/app/worker.py`.

For local development, `backend/setup_backend.sh` starts the worker in the
background before starting Uvicorn. Set `SKIP_WORKER=1` if you only want the API
process.

One worker cycle does this:

1. Recover stale running jobs whose heartbeat expired.
2. Delete expired completed/failed/cancelled job rows.
3. Claim the oldest queued session import job using a database row lock.
4. If no session import job is waiting, claim the oldest queued telemetry
   materialization job.
5. If no work is waiting, clean up expired finished job rows.
6. Load source data through `IngestionService`.
7. Normalize source data into a `SessionSnapshot`.
8. Persist either the full/core session snapshot or the requested telemetry
   segment.
9. Mark the job completed with source/version and row-count metadata.
10. On failure, roll back uncommitted database work and mark the job failed.

The API and worker can run as separate deployed processes that share the same
PostgreSQL database.

In deployment, run the same backend image/codebase with two commands:

- API process: `python -m uvicorn app.main:app`
- Worker process: `python -m app.worker`

## Cleanup Ownership

Session cleanup is worker-owned.

Read paths do not delete expired sessions as a side effect anymore. This keeps
normal API reads predictable and makes data lifecycle an operational concern of
the worker.

Current cleanup behavior:

- expired sessions are hard-deleted when `expires_at < now` and `pinned_at IS NULL`
- completed/failed/cancelled import jobs are deleted after
  `settings.import_job_retention_hours`
- running jobs with stale heartbeats are retried until
  `settings.import_job_max_attempts`, then failed

## Configuration

Relevant settings:

- `ingestion_source`: active source provider, currently `fastf1`
- `session_cache_ttl_hours`: TTL for cached canonical sessions
- `import_job_retention_hours`: how long finished job rows remain
- `import_job_stale_after_minutes`: heartbeat age before a running job is stale
- `import_job_max_attempts`: retry limit for stale jobs
- `import_worker_poll_seconds`: sleep duration when no queued job is available

## API Surface

Create a job:

```http
POST /api/session-import/jobs
```

Request body uses the same shape as `SessionImportRequest`:

```json
{
  "season_year": 2024,
  "round_number": 1,
  "session_name": "Race",
  "source_session_key": "fastf1:2024:1:20240302:bahrain-grand-prix:20240302T150000Z:race",
  "import_profile": "core",
  "force_refresh": false
}
```

Read job status:

```http
GET /api/session-import/jobs/{job_id}
```

List recent jobs:

```http
GET /api/session-import/jobs?limit=25
```

## Database Ownership

Owned by this module:

- `import_jobs`

Referenced by this module:

- `event_sessions`, through `import_jobs.session_id`
- `ingestion_runs`, through `ingestion_runs.job_id`

Owned elsewhere:

- `event_sessions` and all canonical session tables belong to
  [Session Domain](./session-domain.md)
- on-demand telemetry cache orchestration belongs to
  [Telemetry Materialization](./telemetry-materialization.md)
- source loading belongs to [Ingestion](./ingestion.md)
- source-to-canonical conversion belongs to [Normalization](./normalization.md)

## Why No Artifact Store Yet

Artifacts would be justified if one of these becomes true:

- full telemetry imports make PostgreSQL write time the bottleneck
- API reads need large precomputed columnar chunks
- the project needs exact raw-source replay/reprocessing contracts
- deployed storage needs to decouple raw bulk data from relational query data

Until one of those is proven, artifacts would mostly add moving parts without
making FastF1 load itself faster. The current design gets the important benefits
first: profile-based faster imports, background execution, operational status,
retry behavior, and real timing/row-count measurements.
