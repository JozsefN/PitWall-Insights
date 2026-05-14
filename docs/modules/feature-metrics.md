# Feature Metrics

Back to [Backend Architecture](../architecture/02-backend-architecture.md)

## Purpose

The feature-metrics module owns derived, analysis-oriented facts computed from
the canonical session cache.

It is the right home for questions like:

- who has the strongest recent pace
- who is most consistent
- who improved versus the previous lap window
- later, who is attacking, defending, degrading tyres, or gaining by sector

Feature metrics are not raw source data. They are calculated outputs with a
definition, version, input requirements, scope, confidence, and data-quality
metadata.

## Current State

This module is no longer just a health-route stub.

It currently computes three cheap, lap-based metrics on demand:

- `pace_rating`
- `consistency_score`
- `lap_trend`

These v1 metrics use core imported lap data, so they work after a `core`
session import and do not require telemetry materialization.

The module also exposes metric-insight summaries through the decision-engine
rules, but those insights are still considered part of the feature-metric
surface rather than story-feed content.

## Current API

### Health

```http
GET /api/feature-metrics/health
```

Reports available calculators and config version.

### Driver scores

```http
GET /api/feature-metrics/sessions/{session_id}/driver-scores
```

Query parameters:

- `metric_ids`: comma-separated metric ids. Defaults to all v1 metrics.
- `entry_ids`: optional comma-separated `session_entries.id` values.
- `analysis_scope`: defaults to `field`.
- `recent_laps`: defaults to `5`.
- `lap_from`: optional lap lower bound.
- `lap_to`: optional lap upper bound.

If `entry_ids` is supplied while `analysis_scope=field`, the request is
normalized to `explicit_entries`. This keeps selected-driver widgets cheap while
allowing field-wide overview widgets to omit `entry_ids`.

### Metric insights

```http
GET /api/feature-metrics/sessions/{session_id}/insights
```

This route returns rule-selected metric insights such as:

- strongest pace driver
- most consistent driver
- recent improver

Internally this uses the decision engine, but the product meaning is still
feature-metric insight rather than editorial story feed.

## Important Concepts

## Analysis scope

Feature metrics separate what the user selected from what a calculation needs.

Current scope values:

- `field`: compute against every entry in the session
- `explicit_entries`: compute only against supplied `entry_ids`
- `selected_entries`: reserved for frontend-selected driver contexts
- `pair`: reserved for pairwise comparisons
- `lap_window`: reserved for explicit lap-window calculations
- `stint`: reserved for stint-scoped calculations

The current API uses `field` and `explicit_entries` in practice.

This distinction matters because:

- a driver-compare widget should not calculate the whole field
- a "pace leader" insight must compare the whole field
- future overtake probability may only need a pair or nearby group
- future replay widgets may request all position data but selected car telemetry

## Calculator definitions

Every calculator declares metadata:

- metric id
- version
- display name
- description
- supported scopes
- required inputs
- cost level
- output kind
- whether it is API-visible

This makes new metrics additive. A future calculation should be added by
registering a calculator with its requirements, not by rewriting the service.

## Input planning

`application/planner.py` builds a metric plan from the request:

1. resolve requested calculators
2. validate that each calculator supports the requested scope
3. union their required inputs
4. hand that plan to the input provider

Current calculators only require:

- `entries`
- `laps`

Future calculators can declare heavier inputs such as:

- `car_telemetry`
- `position_telemetry`
- `race_control`
- `weather`
- `stints`

Those inputs are not automatically loaded until a calculator or rule asks for
them.

## Input provider

`infrastructure/input_provider.py` loads the canonical data needed by a metric
plan.

Today it supports:

- session existence checks
- session entries
- entry laps

`infrastructure/repository.py` remains as a compatibility alias, but the
preferred name is now `FeatureMetricInputProvider`. This naming is intentional:
feature calculators should depend on analysis input bundles rather than direct
SQL repositories.

## Output shape

Metric scores include:

- `metric_id`
- `metric_version`
- `analysis_scope`
- `comparison_scope`
- `entry`
- `value`
- `rank`
- `confidence`
- `sample_count`
- `window`
- `components`
- `corrections`
- `input_coverage`
- `warnings`

The `comparison_scope` field is important. A score normalized over two selected
drivers is not the same as a score normalized over the whole field.

## Current Calculators

### `pace_rating`

Purpose:

- rank recent clean-lap pace

Inputs:

- entries
- laps

Current method:

1. filter usable laps
2. take the recent lap window
3. calculate median lap time
4. normalize lower median lap time to a higher score
5. rank within the requested comparison scope

Current limitations:

- fuel correction is not applied
- traffic correction is not applied
- tyre-age correction is not applied
- weather correction is not applied

Those omissions are exposed through the `corrections` field instead of hidden.

### `consistency_score`

Purpose:

- rank clean-lap consistency

Inputs:

- entries
- laps

Current method:

1. filter usable laps
2. take the recent lap window
3. calculate median absolute deviation from the median lap time
4. normalize lower variation to a higher score
5. rank within the requested comparison scope

### `lap_trend`

Purpose:

- identify recent lap-time improvement

Inputs:

- entries
- laps

Current method:

1. filter usable laps
2. select a recent clean-lap window
3. select the previous comparable clean-lap window
4. compare recent median against previous median
5. normalize stronger improvement to a higher score

This feeds the current `recent_improver` metric insight.

## Metric Insights

Metric insights are rule-selected facts derived from metric outputs.

Current insight ids:

- `strongest_pace_driver`
- `most_consistent_driver`
- `recent_improver`

These are exposed under:

```http
GET /api/feature-metrics/sessions/{session_id}/insights
```

The rule implementation lives in [Decision Engine](./decision-engine.md), but
the route is exposed here because the product concept is still "feature-metric
insight" rather than story feed.

## Configuration

The module currently uses a code-level config object in:

```text
backend/modules/feature_metrics/infrastructure/config.py
```

Current knobs include:

- recent lap count
- minimum laps for confidence
- pit-lap exclusion
- deleted-lap exclusion
- accuracy filtering
- story/insight thresholds

There is intentionally no database config table yet. A DB-backed rules/config
model can come later once the metric definitions are stable.

## What Belongs Here

- score calculators
- metric definitions
- scope handling
- input planning
- input coverage reporting
- derived lap/telemetry facts
- metric insight API surface

Good future candidates:

- tyre health score
- attack/defend mode
- overtake probability
- strategy window indicator
- cornering advantage maps
- braking intensity
- throttle smoothness
- driver extraction scores

## What Does Not Belong Here

- raw FastF1 access
- canonical lap or telemetry persistence
- editorial/news story feed content
- frontend layout decisions
- direct widget rendering

Those belong in ingestion, session-domain storage, story feed, or the frontend
widget system.

## Future Storage

There are no metric result tables yet.

Current metrics compute on demand from canonical session rows. Later, if metric
latency or reuse justifies it, add storage such as:

- `feature_metric_results`
- `feature_metric_series`
- `feature_metric_runs`

That storage should preserve metric id, version, scope, window, config version,
confidence, components, and input coverage.

## Future Work

- add tests around each calculator and rule
- expose frontend contracts and query hooks for driver scores and insights
- add telemetry-aware calculators behind explicit input requirements
- introduce metric result persistence only when on-demand reads are too slow
- add DB-backed config/rule versions after the v1 formulas settle
