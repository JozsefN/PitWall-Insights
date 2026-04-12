# Feature Metrics

Back to [Backend Architecture](../architecture/02-backend-architecture.md)

## Purpose

The feature-metrics module is the intended home for derived, analysis-oriented metrics that should not be treated as raw source data or core canonical session structure.

Today this module is still mostly a stub, but it already has an important architectural role: it is the boundary that protects the session schema from being overloaded with every computed idea.

## What Belongs Here

Good candidates for this module include:

- acceleration
- distance-driven channels
- relative distance
- driver-ahead and distance-to-driver-ahead
- braking intensity metrics
- corner-segment metrics
- tyre degradation indicators
- widget-specific or dashboard-specific derived series

In general, if a metric depends on calculations, interpolation choices, aggregation, or multiple canonical tables, this module is a strong candidate.

## What Does Not Belong Here

- raw FastF1 car channels
- raw FastF1 position channels
- canonical lap timing fields
- core session reference data

Those belong in ingestion, normalization, and the session-domain schema.

## Current State

Currently the module exposes only a health route and a stub service status.

That is acceptable for now because:

- the raw/canonical session cache had to be built first
- many derived metrics depend on a stable canonical session model

## Why This Separation Matters

Separating canonical session data from feature metrics keeps the system:

- easier to reason about
- easier to debug
- more honest about what is raw versus computed
- more flexible when metric definitions change later

For example, if the team later changes how acceleration or driver-ahead is computed, that should not require redefining the meaning of the canonical raw telemetry tables.

## Likely Future Storage

Possible future tables:

- `session_metrics`
- `entry_metrics`
- `lap_metrics`
- metric-series tables optimized for chart consumers

The exact schema should be designed around query patterns, especially if the frontend starts requesting only one metric series at a time.

## Future Work

- establish raw versus derived metric policy clearly
- add metric computation jobs or on-demand calculation paths
- expose metric-specific endpoints for widgets and charts
