# Architecture Overview

## Goal

This system is a modular motorsport data platform designed to:

- ingest telemetry/session data
- normalize it into a canonical model
- store it
- compute features and metrics
- deliver it via APIs
- render it in a modular frontend

## Philosophy

The architecture is intentionally **thin and modular**:

- Each module has a clear responsibility
- HTTP delivery is centralized
- Domain logic is separated from infrastructure
- The system can evolve without large rewrites

## Current State (Week 1)

- Backend modules exist with skeleton structure
- REST API is functional
- Database connection and migrations are in place
- Frontend skeleton is not yet complete
- Most modules return stub/mock data

## Future Direction

- ingestion pipeline becomes real (file/API ingestion)
- normalization builds canonical session schema
- feature_metrics computes telemetry metrics
- story_feed generates insights
- frontend becomes configurable and modular