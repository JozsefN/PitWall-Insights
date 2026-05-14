# Data Flow

Back to [Frontend Architecture](./03-frontend-architecture.md)

## Core Request Flow

For normal read requests, the backend follows this shape:

Client  
-> FastAPI route  
-> application service  
-> repository  
-> PostgreSQL  
-> JSON response

This is intentionally simple. The route layer owns HTTP concerns, the service layer owns orchestration, and the repository owns direct database access.

## Synchronous Selected-Session Import Flow

The synchronous import route still exists for local/dev and simple clients.

### Step-by-step flow

1. Frontend or client calls `POST /api/sessions/import`.
2. The session route builds a `SessionService`.
3. `IngestionService` calls the FastF1 adapter.
4. The FastF1 adapter:
   - lists or loads the selected session
   - fetches the selected import profile
   - converts source objects to plain record-like data
5. `NormalizationService` builds a canonical `SessionSnapshot`.
6. The session repository persists the snapshot:
   - reference tables first
   - session row
   - entries
   - results
   - laps and stints
   - ticks
   - weather/status/control events
   - telemetry samples
7. The route returns the imported session detail.

## Background Import Job Flow

The preferred deployed flow is job-based:

1. Client calls `POST /api/session-import/jobs`.
2. The API creates an `import_jobs` row with status `queued`.
3. A separate worker process runs `backend/app/worker.py`.
4. The worker claims the oldest queued job.
5. The worker updates progress through:
   - `loading_source`
   - `normalizing`
   - `persisting`
   - `completed` or `failed`
6. The worker loads FastF1 using the job's import profile.
7. The worker persists canonical session data through `SessionRepository`.
8. The client polls `GET /api/session-import/jobs/{job_id}` until the job has
   a terminal status.
9. On success, the job response contains `session_id`.

This lets the API return quickly while long FastF1 loads continue outside the
request/response cycle.

## Import Profile Data Shape

`core` imports write session structure without car/position telemetry.

`full` imports write the same structure plus:

- `car_telemetry_samples`
- `position_samples`

The database records this on `event_sessions.import_profile` and
`event_sessions.telemetry_status`.

## Cached Session Read Flow

For normal archive or detail reads:

1. Frontend calls a session endpoint.
2. Route creates a session service.
3. Repository fetches relational data from PostgreSQL.
4. Domain/Pydantic models shape the response.
5. Frontend consumes the payload through React Query.

Expired-session cleanup is owned by the worker, not by read requests.

## Telemetry Flow

The current telemetry flow separates two concerns:

- per-entry sample ordering
- whole-session alignment

### Per-entry ordering

`car_telemetry_samples` and `position_samples` are ordered by `sample_seq` per `session_entry`.

This is used to answer:

- what comes next for this one driver/car
- how should a telemetry chart render this entry's series

### Whole-session alignment

`session_ticks` are built from the union of observed timestamps across:

- lap boundaries
- sectors
- weather samples
- status events
- track status events
- race control messages
- car telemetry
- position telemetry

This is used to answer:

- what was happening across the field at this moment
- how can replay-style consumers align multiple entries

## Auth Flow

The auth flow is separate from session import and currently works like this:

1. Client signs up or logs in
2. Backend validates credentials and returns a bearer token
3. Frontend stores the token in local storage
4. Axios attaches the token to future requests
5. `/api/auth/session` decodes the token and returns a lightweight auth-session payload

## Feature Metrics Flow

Feature metrics sit after canonical session storage.

Current score flow:

1. Client calls `GET /api/feature-metrics/sessions/{session_id}/driver-scores`.
2. The route builds a `FeatureMetricsService`.
3. The service creates a `FeatureMetricDriverScoreRequest`.
4. `application/planner.py` resolves calculators and required inputs.
5. `FeatureMetricInputProvider` loads only those inputs from canonical session
   tables.
6. Calculators compute scores and return confidence, scope, components,
   corrections, and input coverage.

Current v1 metrics use only entries and laps:

- `pace_rating`
- `consistency_score`
- `lap_trend`

This means they can run after a `core` import without telemetry
materialization. It also means metric widgets can request compact derived
payloads instead of pulling full raw telemetry.

## Metric Insight and Decision Flow

Metric insights use the decision engine:

1. Client calls `GET /api/feature-metrics/sessions/{session_id}/insights`.
2. The feature-metrics route builds a `DecisionEngineService`.
3. The decision engine resolves requested rules.
4. Each rule declares the feature metrics it needs.
5. `FeatureMetricsService` computes those metrics for the requested scope.
6. Rules emit signals when configured thresholds and confidence gates pass.

The lower-level diagnostic route is:

```http
GET /api/decision-engine/sessions/{session_id}/signals
```

Current rules are:

- `strongest_pace_driver`
- `most_consistent_driver`
- `recent_improver`

## Story Feed Flow

Story feed is not currently connected to session metric insights.

For now it only exposes health/status:

```http
GET /api/story-feed/health
```

It is reserved for future season/news/history content such as official videos,
headline stacks, race-week rhythm, and follow-up stories from previous races.
