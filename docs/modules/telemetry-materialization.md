# Telemetry Materialization

Back to [Backend Architecture](../architecture/02-backend-architecture.md)

## Purpose

Telemetry materialization owns on-demand telemetry caching for an already
imported session.

The session id remains the stable identity. Lookback mode, simulation mode,
driver selection, lap selection, and widgets are consumers of that same session;
they do not create separate sessions.

## Design

Core session import is the fast path. It loads metadata, entries, laps, stints,
weather, status, race control, and a basic timeline.

Telemetry is cached later as additive segments:

- session id
- session entry id
- telemetry kind: `car` or `position`
- scope: `session` or `lap`
- lap number when scope is `lap`

Once a segment is loaded, it is reusable by any mode. Loading VER lap 9 car data
for lookback does not get deleted when the user switches to simulation. Loading
session-scope position data later adds more cache coverage to the same session.

## Workflow

1. The frontend opens a core session.
2. A widget asks for the telemetry shape it needs.
3. The frontend calls:

```http
POST /api/telemetry/materialization/ensure
```

4. If matching cache segments already exist, the response is immediately ready.
5. If not, a telemetry materialization job is queued.
6. The worker loads source telemetry, normalizes it, and persists only the
   requested slice.
7. Widgets query the normal session telemetry endpoints after the segment is
   ready.

The worker process must be running for queued jobs to move. In local
development that means running `python -m app.worker` from `backend/`, or using
`backend/setup_backend.sh`, which starts the worker unless `SKIP_WORKER=1` is
set.

## Queue Behavior

Telemetry widgets can change their requested entry set quickly, especially in
simulation mode when the user selects many drivers. The materialization queue
therefore treats broader queued jobs as superseding narrower queued jobs for
the same session, telemetry scope, lap, and kind.

Current behavior:

- `ensure` returns an existing active job when that job already covers the
  missing entry/kind pairs.
- if a broader job is queued, older queued subset jobs are marked `cancelled`
  instead of staying ahead of the useful work.
- the worker claims the broadest queued telemetry materialization job first,
  so a 20-driver replay request does not wait behind a staircase of 1-driver,
  2-driver, and 3-driver requests.
- running jobs are not cancelled underneath the worker; only queued jobs are
  superseded.

The frontend should treat `cancelled` as a terminal job state. It is not an
error for the user; it means a more complete cache request replaced stale work.

## Why This Exists

Full-session telemetry can be hundreds of thousands of rows. Automatically
writing all telemetry for every opened session made the first usable experience
too slow.

This module keeps the benefits of PostgreSQL-backed normalized telemetry while
avoiding a full artifact system too early.

## Database Ownership

Owned by this module:

- `telemetry_cache_segments`
- `telemetry_materialization_jobs`

Referenced by this module:

- `event_sessions`
- `session_entries`
- `car_telemetry_samples`
- `position_samples`
- `session_ticks`

The canonical telemetry sample tables still belong to the session domain. This
module decides when a subset of those tables should be populated.

## Mode Semantics

Modes do not own data.

- Lookback usually requests selected drivers and a selected lap.
- Simulation usually requests session-scope position data and selected driver
  car data.
- Both modes reuse any segment that already exists.
- Session-scope data satisfies lap-scoped reads for the same entry and kind.

## Future Path

If PostgreSQL becomes too slow for large telemetry reads, this module becomes
the boundary where artifact-backed storage can be introduced. Widget code should
still ask for a telemetry segment; only the implementation behind the segment
would change.
