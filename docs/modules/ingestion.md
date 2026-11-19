# Ingestion

The active provider is OpenF1. The provider registry constructs OpenF1Adapter;
source selection is not part of the user workflow.

## Responsibilities

- OpenF1Catalog obtains meetings and sessions directly from OpenF1.
- OpenF1Adapter loads a selected historical session and maps source rows to SourceSessionBundle.
- OpenF1Client owns HTTP access, response validation, request limits and bounded transient retries.
- OpenF1ResponseCache owns compressed files, expiry and atomic replacement across processes.
- Core imports include drivers, laps, stints, weather, race control and available source reports.
- Full materialization fetches only the selected drivers and requested car/location streams.
- The normalization module converts the bundle to the canonical SessionSnapshot.

Native keys use `openf1:meeting:<meeting_key>` and `openf1:session:<session_key>`.
The calendar identifies completed history, upcoming sessions and cancellations.
The data path permits history after the provider's post-session waiting period.

## Cache and limits

Successful responses are stored as compressed JSON outside the repository in
`%LOCALAPPDATA%/pitwall-insights/openf1` on Windows, or the platform cache directory.
The calendar uses a short cache lifetime; historical responses have a longer one.
The cache is disposable. PostgreSQL holds the normalized application data.

`openf1_adapter.py` handles session identity and race-data conversion;
`openf1_client.py` handles HTTP; `openf1_cache.py` handles disposable files.
The adapter and calendar use the same client contract. These are Python
components of the API/worker processes, not separately deployed services.

Requests use bounded connect/read timeouts, a bounded response size and a local
rate limiter shared by clients in one process. Timeouts, connection failures and
HTTP 429/502/503/504 receive at most three attempts. Retry-After is respected; a
provider wait exceeding the bounded retry window returns an actionable failure
instead of retrying too early. Authentication and permanent HTTP errors do not retry.
Empty or malformed telemetry does not count as a successful complete
materialization. Missing optional resources are recorded in coverage metadata.
Multiple deployed processes would need a shared provider rate limiter.

Cached content is validated before reuse. Corrupt, expired, empty or incorrectly
shaped responses fall back to HTTP. Writers use unique temporary files and atomic
replacement, so processes cannot share the same in-progress filename. Cache-write
failures are logged and do not discard an already validated download. PostgreSQL
remains responsible for durable normalized session data.

## Quality and calculations

The adapter retains native lap, pit-stop, interval and race-position reports.
`openf1_clean_lap_v1` computes conservative lap eligibility from observed clocks,
sectors, flags, pit events and deletions. Unknown evidence stays unknown.
Normalization aligns units and timestamps; feature_metrics computes derived values.
Neither layer invents unavailable engineering measurements.

The project's selected historical testing scope is 2023-2025. The provider's
history starts in 2023; 2025 is the project test boundary, not a provider-wide maximum.
The [decision history](../architecture/11-hybrid-data-and-accounts.md) explains how
the application reached this architecture.
