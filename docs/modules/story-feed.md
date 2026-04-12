# Story Feed

Back to [Backend Architecture](../architecture/02-backend-architecture.md)

## Purpose

The story-feed module is the intended home for insight generation, editorial summaries, and higher-level narrative outputs built on top of session data.

This is not the place for raw ingestion or canonical storage. It is where the system can later answer questions like:

- what changed in the race over the last ten laps
- which drivers are gaining or losing time in meaningful ways
- what story should be highlighted to the user right now

## Current State

Today the module is still a placeholder with a health route and stub service status.

That is expected. The project first needed:

- authentication basics
- a stable session cache
- ingestion and normalization boundaries

Only after those exist does it make sense to build reliable insight generation on top.

## Likely Responsibilities Later

- generate narrative summaries from session or metric inputs
- rank notable events or trends
- provide feed items for archive or live-session views
- translate telemetry and metric changes into user-facing explanations

Depending on product direction, this module could eventually support:

- rule-based insight generation
- prompt-driven summarization
- ML-assisted ranking or explanation

## Inputs This Module Will Probably Need

The story feed should consume already-structured data from other modules, especially:

- canonical session data from `session_domain`
- derived series and scoring outputs from `feature_metrics`
- race control and track-status context

This keeps the module focused on interpretation rather than raw data wrangling.

## What Does Not Belong Here

- direct FastF1 access
- canonical lap/telemetry persistence
- low-level derived metric math
- auth/session-token logic

Those concerns belong in ingestion, session-domain storage, feature metrics, and identity auth.

## Future Work

- define a story item contract for frontend consumption
- decide whether stories are precomputed, on-demand, or hybrid
- connect to feature metrics once derived telemetry analytics are available
- add ranking and explanation logic for live and archive experiences
