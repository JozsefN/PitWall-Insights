# API Design

Back to [Backend Architecture](./02-backend-architecture.md)

## API Style

The backend exposes a REST-style JSON API through FastAPI.

Characteristics:

- route groups are organized by module
- requests are mostly resource-oriented
- module routes are mounted in one central router
- the API currently favors straightforward list/detail endpoints over highly nested page-specific responses

## Route Groups

### Health

- `GET /health`
- `GET /api/health`

Purpose:

- quick liveness checks
- database connectivity visibility

### Auth

- `GET /api/auth/health`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `GET /api/auth/session`

Purpose:

- user registration and login
- lightweight bearer-token session inspection

### Sessions

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

Purpose:

- browse available source sessions
- import one selected session into cache synchronously
- inspect cached sessions
- read entry-level details and time-series data

### Session Import Jobs

- `POST /api/session-import/jobs`
- `GET /api/session-import/jobs`
- `GET /api/session-import/jobs/{job_id}`

Purpose:

- create background imports
- poll import progress
- separate slow source loading from normal API request duration

### Module Health Routes

- `GET /api/ingestion/health`
- `GET /api/normalization/health`
- `GET /api/feature-metrics/health`
- `GET /api/story-feed/health`

Purpose:

- report module readiness/status
- expose whether supporting modules are still stubs or active

## Current API Consumers

The frontend already consumes:

- auth session endpoints
- session list
- session detail

The backend exposes more than the frontend currently uses. This is expected at the current stage of the project.

The frontend can keep using `POST /api/sessions/import` while the async flow is
wired into the product. The job API is ready for the deployed worker model.

## API Resource Design Notes

### Session-first design

The API is organized around the session cache rather than around generic telemetry tables.

This is a good fit for the current product because the main user journey is:

- choose a session
- import/open it
- inspect entries, laps, telemetry, and future metrics

### Entry-scoped telemetry

Telemetry is currently exposed under a session entry:

- `.../entries/{entry_id}/telemetry/car`
- `.../entries/{entry_id}/telemetry/position`

This matches the database design, where raw samples belong to a `session_entry`.

### Replay-aligned reads

`GET /api/sessions/{session_id}/ticks` exists to support future replay and aligned multi-entry consumers.

### Future extension path

The current route shape can later support:

- field filtering
- time-window filtering
- downsampling
- metric-specific series endpoints

Examples of likely future additions:

- `GET /api/sessions/{id}/entries/{entryId}/telemetry/car?fields=speed_kph,rpm`
- `GET /api/sessions/{id}/entries/{entryId}/metrics/braking`
- `GET /api/sessions/{id}/replay/frame?tick_no=12345`

## Related Docs

- [Session Domain](../modules/session-domain.md)
- [Identity Auth](../modules/identity-auth.md)
- [Database and Migrations](./06-database-and-migrations.md)
