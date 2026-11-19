# Architecture Home

This folder describes how PitWall-Insights is structured today and where the project is heading next.

The goal of these docs is practical clarity:

- explain how the current backend and frontend are organized
- show how data moves through the system
- document the current database model and module boundaries
- make future changes easier to place in the right layer

## Recommended Reading Order

1. [Overview](./00-overview.md)
2. [System Architecture](./01-system-architecture.md)
3. [Backend Architecture](./02-backend-architecture.md)
4. [Frontend Architecture](./03-frontend-architecture.md)
5. [Data Flow](./04-data-flow.md)
6. [API Design](./05-api-design.md)
7. [Database and Migrations](./06-database-and-migrations.md)
8. [Dashboard Builder](./07-dashboard-builder-foundation.md)
9. [Widget Creation Runbook](./widget-creation-runbook.md)
10. [Replay Loading and Startup Target](./08-replay-loading.md)
11. [Backend F1 Analytics and Extension Runbook](./09-f1-analytics.md)
12. [F1 Metric Catalogue](./f1-metric-catalog.md)
13. [Strategy Foundation, Methods and Runbook](./10-strategy-foundation.md)
14. [Decision-oriented Strategy Catalogue](./strategy-metric-catalog.md)
15. [Physics-informed Race Estimation and Panel Runbook](./12-race-estimation.md)
16. [Race Estimation Calculation Catalogue](./race-estimation-catalog.md)
17. [Adatforrás-váltás és végleges OpenF1-architektúra](./11-hybrid-data-and-accounts.md)

18. [Session Review Analytics and Calibration](./13-session-review.md)

## Module Reference

### Backend Modules

- [Session Domain](../modules/session-domain.md)
- [Session Import](../modules/session-import.md)
- [Identity Auth](../modules/identity-auth.md)
- [Ingestion](../modules/ingestion.md)
- [Normalization](../modules/normalization.md)
- [Feature Metrics](../modules/feature-metrics.md)
- [Decision Engine](../modules/decision-engine.md)
- [Story Feed](../modules/story-feed.md)

### Frontend Modules

- [Frontend App Shell](../modules/frontend-app-shell.md)
- [Frontend Data Layer](../modules/frontend-data-layer.md)
- [Frontend Auth](../modules/frontend-auth.md)
- [Frontend Sessions Workspace](../modules/frontend-sessions.md)
- [Frontend Widget System](../modules/frontend-widget-system.md)

## Current Architectural Direction

The current architecture is centered on one main workflow:

1. discover a Formula 1 session
2. import it from OpenF1
3. optionally run that import through a background job
4. normalize it into a canonical internal snapshot
5. store it in a relational selected-session cache
6. expose it through API resources for frontend views and future replay-style tooling

This means the most important active modules right now are:

- `ingestion`
- `normalization`
- `session_import`
- `session_domain`
- `delivery_api`

`feature_metrics` owns the existing lap scores/insights and the separate [backend F1 analytics service](09-f1-analytics.md), with 137 versioned calculations, cached summaries and point-in-time car state. See the [metric catalogue](f1-metric-catalog.md) for exact definitions. `decision_engine` selects meaningful rule-based signals from the original scores. `story_feed` remains planned for future season/news/history content rather than current-session metric cards.

## What Changed Recently

The backend has moved beyond the original placeholder session model.

It now includes:

- an OpenF1-backed ingestion path
- profile-based `core` and `full` imports
- import jobs and a worker entrypoint
- an entry-centric session model
- laps, stints, weather, status, and race-control storage
- per-entry raw telemetry tables
- session-wide tick alignment for replay-oriented reads
- lap-based feature metrics for pace, consistency, and recent trend
- rule-selected metric insights for pace leader, consistency leader, and recent improver

The docs in this folder have been expanded to reflect that newer architecture rather than the original scaffold-only state.

## Documentation Scope

These docs are intentionally architecture-focused.

They do not try to replace:

- endpoint-level API examples in code or OpenAPI
- inline code comments near tricky implementation details
- future operational runbooks

Instead, they explain where responsibilities live and why.
