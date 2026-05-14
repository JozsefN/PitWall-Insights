# Decision Engine

Back to [Backend Architecture](../architecture/02-backend-architecture.md)

## Purpose

The decision-engine module owns rule-based selection of meaningful signals from
feature metrics.

It does not calculate raw metrics itself. It consumes metric outputs and decides
which ones are worth highlighting.

In the current architecture:

```text
canonical session data
-> feature metrics
-> decision engine
-> metric insights API
```

The decision engine is intentionally separate from story feed. A signal such as
"driver X has the strongest pace rating" is a metric insight, not a paddock news
story or season narrative.

## Current State

The module currently implements three v1 rules:

- `strongest_pace_driver`
- `most_consistent_driver`
- `recent_improver`

These rules consume the current cheap lap-based feature metrics:

- `pace_rating`
- `consistency_score`
- `lap_trend`

## Current API

### Health

```http
GET /api/decision-engine/health
```

Reports available rules and rule definitions.

### Signals

```http
GET /api/decision-engine/sessions/{session_id}/signals
```

Query parameters:

- `signal_ids`: optional comma-separated signal ids
- `entry_ids`: optional comma-separated session entry ids
- `analysis_scope`: defaults to `field`
- `recent_laps`: defaults to `5`
- `lap_from`: optional lap lower bound
- `lap_to`: optional lap upper bound

This lower-level route exists for debugging, diagnostics, and future internal
consumers. Product-facing metric insight cards are exposed through:

```http
GET /api/feature-metrics/sessions/{session_id}/insights
```

## Rule Definition Contract

Each rule declares:

- signal id
- version
- display name
- description
- required metrics
- supported scopes
- default scope
- severity

This mirrors feature-metric calculator metadata and keeps future rules
additive.

## Current Rules

### `strongest_pace_driver`

Required metric:

- `pace_rating`

Behavior:

- picks the top-ranked pace score in the requested scope
- requires configured minimum confidence
- requires configured pace threshold

### `most_consistent_driver`

Required metric:

- `consistency_score`

Behavior:

- picks the top-ranked consistency score in the requested scope
- requires configured minimum confidence
- requires configured consistency threshold

### `recent_improver`

Required metric:

- `lap_trend`

Behavior:

- picks the strongest recent-vs-previous lap-window improvement
- requires configured minimum confidence
- requires configured improvement threshold

## Signal Shape

Decision signals include:

- signal id and version
- session id
- primary entry
- title
- summary
- severity
- confidence
- evidence
- data quality/input coverage
- computed timestamp

The `evidence` field points back to the metric id, metric version, value, rank,
comparison scope, and metric components that caused the rule to emit.

## Boundaries

### Belongs here

- deciding which metric result matters
- thresholding and confidence gates
- signal metadata and severity
- rule definitions

### Does not belong here

- raw lap or telemetry SQL
- metric formulas
- news/headline/story aggregation
- frontend presentation

Those belong in feature metrics, story feed, or frontend widgets.

## Future Work

- add signal tests
- add rule groups for live overview, replay, and strategy contexts
- add telemetry-expensive rules only when their required inputs can be planned
  and materialized safely
- eventually support persisted rule/config versions if operators need to tune
  thresholds without code changes
