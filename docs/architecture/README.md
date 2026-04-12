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

## Module Reference

### Backend Modules

- [Session Domain](../modules/session-domain.md)
- [Identity Auth](../modules/identity-auth.md)
- [Ingestion](../modules/ingestion.md)
- [Normalization](../modules/normalization.md)
- [Feature Metrics](../modules/feature-metrics.md)
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
2. import it from FastF1
3. normalize it into a canonical internal snapshot
4. store it in a relational selected-session cache
5. expose it through API resources for frontend views and future replay-style tooling

This means the most important active modules right now are:

- `ingestion`
- `normalization`
- `session_domain`
- `delivery_api`

`feature_metrics` and `story_feed` are intentionally present early so the eventual architecture has somewhere clean to put derived analysis and editorial insight logic without overloading the canonical session schema.

## What Changed Recently

The backend has moved beyond the original placeholder session model.

It now includes:

- a FastF1-backed ingestion path
- an entry-centric session model
- laps, stints, weather, status, and race-control storage
- per-entry raw telemetry tables
- session-wide tick alignment for replay-oriented reads

The docs in this folder have been expanded to reflect that newer architecture rather than the original scaffold-only state.

## Documentation Scope

These docs are intentionally architecture-focused.

They do not try to replace:

- endpoint-level API examples in code or OpenAPI
- inline code comments near tricky implementation details
- future operational runbooks

Instead, they explain where responsibilities live and why.
