# Overview

Back to [Architecture Home](./README.md)

## What PitWall-Insights Is

PitWall-Insights is a motorsport data platform centered on Formula 1 session exploration, replay-style analysis, and future live-race support.

The current product direction has four major capabilities:

- import a selected historical session from FastF1
- normalize that session into a stable internal schema
- expose the cached session through backend APIs
- power archive, telemetry, and future metric-driven frontend surfaces

## Core Product Idea

The project is not trying to be a generic data lake. The current architecture is optimized around one practical workflow:

1. choose a session
2. import it on demand
3. normalize it into an entry-centric schema
4. query it for archive views, telemetry views, and later replay or analysis widgets

That decision affects almost every layer:

- ingestion is source-aware
- normalization creates one canonical internal shape
- storage keeps selected sessions temporarily
- APIs expose session-focused resources

## Current State

Today the repository contains:

- a FastAPI backend in `backend/`
- a React frontend in `frontend/`
- architecture and module documentation in `docs/`
- a PostgreSQL schema managed through Alembic

The backend is meaningfully ahead of the frontend at the moment. The backend already includes:

- auth endpoints
- health endpoints
- a session catalog/import/cache API
- a relational schema for sessions, entries, laps, stints, telemetry, and ticks
- on-demand feature metrics for pace rating, consistency score, and recent lap trend
- rule-selected metric insights for pace leader, consistency leader, and recent improver
- a planned story-feed namespace for future season/news/history content

The frontend currently:

- handles app layout and navigation
- uses React Query and Axios for API communication
- consumes auth and basic session APIs
- still renders many pages as placeholders

## Guiding Architectural Principles

- Prefer explicit module boundaries over shared magic.
- Keep source-specific logic in ingestion, not spread across the whole backend.
- Keep canonical session structure in normalization and session-domain storage.
- Keep derived metrics separate from raw imported data.
- Keep rule-selected metric insights separate from editorial story-feed content.
- Model the driver/car combination as a first-class session entry.
- Optimize for readability and future change, not the shortest possible implementation.

## Where To Go Next

- [System Architecture](./01-system-architecture.md) for the high-level pipeline
- [Backend Architecture](./02-backend-architecture.md) for code organization
- [Data Flow](./04-data-flow.md) for request and import lifecycles
- [Database and Migrations](./06-database-and-migrations.md) for the current relational model
- [Session Domain](../modules/session-domain.md) for the core motorsport data model
