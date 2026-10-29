# Backend readiness — 2026-10-18

The later [strategy validation report](strategy-validation.md) records the expanded 66-test backend suite and current strategy APIs/migrations. The measurements below remain the original replay/diagnostic baseline for this date.

The available-data replay startup target was met through the real API, queue, worker, PostgreSQL writes and full-grid reads. An uncached provider download for the affected 2026 Chinese GP remains externally blocked; that limitation is reproduced separately rather than counted as a successful load.

## Measured results

| Check | Result | Evidence |
| --- | --- | --- |
| Empty database telemetry cache, Italian GP 2025, 20 drivers, both streams, existing provider files | **93.687 s** to all initial replay reads; target 180 s | [Full-grid benchmark](replay-readiness-final.json) |
| Preparation portion of that run | 87.843 s; 1,206,220 original samples persisted | Same benchmark |
| Worker stages | Source 8.04 s; normalization 11.70 s; persistence 65.27 s; total 85.01 s | Local `%TEMP%/pitwall-ready-worker-final-error.log` |
| All 40 sampled driver/stream responses | Full race range through the finish, at 500 ms sampling | Full-grid benchmark sample bounds |
| Cached replay in production-build Chromium | 8.32 s playable, 20 drivers | `frontend/tests/replay.e2e.py` |
| Unavailable-source error in Chromium | 6.54 s | Same browser runner |
| New complete analytics, Miami 2025 | 5.547 s, 137 definitions, 2,417 entry/session results | [Analysis benchmark](analytics-benchmark-2026-10-18.json) |
| Cached complete analytics without concurrent test load | 0.031 s; no car/position sample queries | [Cache benchmark](analytics-cache-benchmark-2026-10-18.json), integration assertions |
| Indexed 20-car point-in-time state | 0.047 s; all 20 positions fresh | Cache benchmark |
| Real analysis input | 213,840 car records, 213,820 position records, 94 weather records, 22 track-status records, 55 in-window race-control messages | Analysis benchmark |
| Worker / schema / cleanup | Ready, one live worker, no queued/running jobs, revision `e1b826a3f945`, no leftover test schemas or replay benchmark fixtures | [Final health](backend-health-final.json) |

The new-analysis benchmark overlapped regression-test activity: its immediately repeated cached request took 1.875 s during that load. A separate idle cache run measured 0.031 s. These are local measurements, not a production concurrency SLA. Analytics uses pre-existing materialized data and is not part of replay preparation.

The database-empty replay test retains FastF1's provider disk cache. It does not establish the time for a successful brand-new network download. Earlier independent database-empty full-grid runs measured 75.235 s and 90.906 s; the final worker implementation measured 93.687 s. Each fixture cloned only metadata and was removed afterward; original telemetry was preserved.

## External source limit

[Captured source responses](replay-source-access.json) show both car and position URLs for the affected Chinese GP returning F1 archive **401**, with mirror **404**, in roughly 0.2–0.4 seconds per request. No account credentials were used, and source caches were not modified. [FastF1 issue 978](https://github.com/theOehrly/Fast-F1/issues/978) reports the upstream access restriction.

The application can prepare available provider data in less than three minutes and report unavailable source data promptly. It cannot deliver telemetry withheld by both configured upstream sources. Repeated retries or deleting functioning provider caches do not resolve that authorization failure.

## Completed checks

- **39 backend tests pass**, including pure numerical ground truths, disposable-schema API/worker integration, real live API authentication and sampled replay reads, and fresh Alembic migration history.
- **14 frontend unit tests pass**, including clamp-at-size-limits, layouts, sampling and token renewal.
- **Replay browser workflow passes**: full-grid selection, one shared active-token renewal, whole-race sample coverage, visible map/cards, playback, pause, seek to finish, unavailable-source feedback and expired-token sign-in. No browser runtime errors.
- **Dashboard-builder browser workflow passes**: widget catalogue, distinct previews, drag/resize, minimum/aspect rules, group overview/reordering, persistence/save retry, edit/reload, protected built-ins/copying, favorites, account isolation, mobile stacking and deletion/discard. No browser runtime errors.
- `alembic upgrade head`, **`alembic check`**, compile checks and **`pip check` pass**. No pending ORM schema changes remain.
- The actual migration test installs through `c9f604e1d723` in an empty disposable schema, reproduces legacy wind units, upgrades to head, checks metadata alignment, verifies the repair is not repeated, downgrades, upgrades again and checks alignment once more. The public schema is not migrated by this test.
- Final cleanup confirms zero temporary schemas and zero isolated replay fixtures. Test and benchmark accounts are removed by their runners.

Materialization integration specifically checks eight concurrent ensure requests creating one job, parallel workers sharing ticks, actual COPY writes and cache reuse, lap scope, refresh, stale recovery, source failure/retry, entry validation, authentication and live/stale/offline worker presence. Message refresh is tested for idempotency and for associating the entire roster even when only one other driver's telemetry was requested.

Analytics integration checks every registered calculation emits a result; missing data, time/lap/entry filters, unsupported selections, cache hits without sample reads, invalidation, bounded cache storage, work limits, busy responses and source changes during computation. Actual database locks are tested to block a second connection in the same schema while allowing an independent translated test schema. Numerical tests independently verify units, acceleration, braking energy, tyre slope, circular direction, geometry, gaps/spikes, false incident exclusions, exact driver attribution and event filtering/capping. Inferred crash/off-track candidates remain explicitly distinct from confirmed observations.

## Database changes

- `a7d4e2c9b501`: recheck legacy empty full-session telemetry segments.
- `b8e5f3d0c612`: concurrent car/position lap/stint indexes.
- `c9f604e1d723`: worker heartbeat table and diagnostic readiness.
- `d0a715f2e834`: versioned analysis cache and one-time FastF1 wind-unit repair.
- `e1b826a3f945`: missing driver/team/race-control-entry foreign-key indexes. ORM declarations now reuse existing composite/explicit indexes rather than implying sixteen additional duplicate indexes. The pre-existing job-session index name is retained.

## Reproduction

From the root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

With the local API and worker running, from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe scripts/benchmark_replay.py e936a667-210e-4017-ac5c-22088e7da720 --drivers 20 --isolated
.\.venv\Scripts\python.exe scripts/benchmark_analysis.py 83b766df-f250-4293-8b72-15f481ea039b
.\.venv\Scripts\python.exe scripts/probe_replay_source.py 5ee16b1e-792f-49c1-ad14-952aea673507
```

The IDs above identify this local dataset; the benchmark scripts accept other imported sessions. A repeated analytics request is a cache measurement, not another cold computation; its `first_request_cache_hit` field makes this explicit. The source probe checks response headers without downloading whole feeds.

From `frontend`, `npm.cmd test` runs unit tests. The Python Playwright runners can target a running dev server or production preview using `PITWALL_FRONTEND_URL`. The recorded browser run used `http://127.0.0.1:4173`; screenshots and timings are under `%TEMP%/pitwall-replay-e2e` and `%TEMP%/pitwall-layout-builder-e2e`.

See [replay architecture](../architecture/08-replay-loading.md), [analytics contracts and extension runbook](../architecture/09-f1-analytics.md), and the [137-metric catalogue](../architecture/f1-metric-catalog.md).
