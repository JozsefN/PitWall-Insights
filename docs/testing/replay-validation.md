# Replay validation — 2026-10-18

Measurements use the running local PostgreSQL-backed API, real provider cache files and actual Chromium. No existing profile credentials were used. Temporary accounts and isolated benchmark sessions are cleaned up. Existing source/session data is retained.

| Scenario | Result |
| --- | --- |
| 20-driver cached telemetry, API timeline/ensure plus all sampled car/position reads, Miami 2025 | 8.859 seconds |
| Cached 20-driver replay playable in Chromium production build, including active token renewal | 8.294 seconds (development run under concurrent benchmark load: 19.17 seconds) |
| Empty database telemetry cache, 20 drivers, Italian GP 2025, existing FastF1 provider disk cache, final indexes applied | 75.235 seconds including all sampled data reads; preparation complete at 68.969 seconds |
| Samples written in that isolated full-grid test | 1,206,220 |
| Full-grid worker stages | Source 8.43 s; normalization 12.02 s; persistence 46.01 s; worker total 66.46 s |
| Empty database telemetry cache, two drivers, before COPY optimization | 35.594 seconds including reads; persistence 27.98 seconds |
| Affected Chinese GP 2026 source failure displayed in Chromium production build | 4.466 seconds |
| Direct source requests for affected session | F1 archive 401; FastF1 mirror 404 |

These distinguish a cold **database** cache from an uncached **provider download**. A successful fresh-download benchmark is blocked by the upstream archive access failure. No claim is made that uncached blocked sessions can become playable within three minutes.

The final full-grid machine-readable result is [replay-benchmark-2026-10-18.json](replay-benchmark-2026-10-18.json). All 40 car/position responses contain samples through the race time range. The fixture was removed successfully after measurement.

## Coverage

- All 14 Node tests and 11 backend tests pass. Frontend build and ESLint pass; the existing non-blocking bundle-size warning remains.
- Node tests cover full replay clock bounds, exact final time, long sessions, bounded sample counts and token renewal timing.
- Backend tests cover selected driver/kind extraction, parsed-session reuse, explicit refresh, unavailable-source rejection, legacy empty cache segments, sampled read ordering/ranges and final coverage, unchanged raw reads, and valid/expired/missing/deleted-user token renewal.
- Live database COPY tests verify actual inserted counts, duplicate suppression, empty inputs, foreign-key enforcement, heartbeat callbacks and rollback.
- Both migrations are applied through `b8e5f3d0c612`. All four lap/stint relationship indexes are valid; EXPLAIN confirms the lap lookup uses the new index rather than a full sample-table scan.
- Browser tests use 20 drivers, verify one renewal for concurrent requests, preserve replay URL selections, render the map/cards, start/pause playback, move positions, seek to the exact finish, report real source failure and return expired sessions to sign-in. No browser runtime errors were observed.
- The existing layout-builder workflow remains part of regression validation.

## Reproduce

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

In a second terminal:

```powershell
cd frontend
npm.cmd run dev
npm.cmd run test
npm.cmd run lint
npm.cmd run build
```

From `backend`, with API and worker running:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/benchmark_replay.py 83b766df-f250-4293-8b72-15f481ea039b --drivers 20
.\.venv\Scripts\python.exe scripts/benchmark_replay.py e936a667-210e-4017-ac5c-22088e7da720 --drivers 20 --isolated
```

The isolated benchmark clones only session/entry/lap/stint metadata under a generated ID, prepares actual telemetry through the real queue/worker and reads it through the API, then removes only that fixture. It never deletes telemetry from the original session. The required provider files must already exist locally while the upstream archive is restricted. Fixture cleanup time is excluded from startup timing.

From the repository root using Python with Playwright/Chromium installed:

```powershell
python frontend/tests/replay.e2e.py
python frontend/tests/layout-builder.e2e.py
```

The browser replay runner currently uses the existing Miami 2025 and Chinese GP 2026 session IDs in this local dataset. Screenshots and timings are written to `%TEMP%\pitwall-replay-e2e`. The API benchmark accepts any imported session ID.
