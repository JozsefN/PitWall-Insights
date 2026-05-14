# Story Feed

Back to [Backend Architecture](../architecture/02-backend-architecture.md)

## Purpose

The story-feed module is reserved for season, race-week, and paddock-facing
content rather than current-session metric calculations.

It should eventually power product surfaces like:

- official video wall
- headline stack
- race-week rhythm
- follow-up stories from previous races this season
- broader context around teams, drivers, and championship narratives

This definition is intentionally different from feature-metric insights.

## Current State

The module currently exposes only:

```http
GET /api/story-feed/health
```

The health payload reports:

- `feed_name: season_story_feed`
- `status: planned`
- `enabled: false`
- planned surfaces such as official videos, headlines, race-week rhythm, and
  season follow-up stories

There is no active story-item session route right now.

## Why Metric Insights Do Not Belong Here

Outputs such as:

- "Driver X has the strongest pace rating"
- "Driver Y is most consistent"
- "Driver Z improved over the last five laps"

are not story-feed content in the current product definition.

They are feature-metric insights:

```text
feature metrics calculate facts
decision engine selects the important fact
feature metrics exposes the insight surface
```

Those current insight cards live under:

```http
GET /api/feature-metrics/sessions/{session_id}/insights
```

Story feed should not become a dumping ground for live/session analytics.

## Future Responsibilities

Likely future story-feed responsibilities:

- ingest or reference official F1 videos and related clips
- collect headline/news items from approved sources
- group stories by race week, session, driver, team, or season thread
- surface previous-race context for the current weekend
- connect official/media content with imported session context

Depending on product direction, it may later use:

- manual/source-provided metadata
- rule-based story grouping
- prompt-driven summaries
- embeddings/search over season story history

## Inputs This Module May Need Later

Possible inputs:

- official video metadata
- external headline/news feeds
- race-week schedule/session metadata
- imported session summaries
- feature-metric insights as optional context
- championship standings and prior race outcomes

Feature metrics may inform a story later, but they should not be the story feed's
primary calculation surface.

## What Does Not Belong Here

- low-level feature metric calculations
- decision-engine thresholds for current-session signals
- raw FastF1 access
- canonical session persistence
- frontend widget rendering

Those concerns belong in feature metrics, decision engine, ingestion, session
domain, or the frontend.

## Future Work

- define a true story item/source contract
- decide source strategy for official videos and headlines
- add season/race-week query routes
- connect the frontend placeholder story-feed page to real content once a
  source strategy exists
