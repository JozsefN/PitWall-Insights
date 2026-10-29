# Strategy validation — 2026-10-18

The implemented strategy foundation contains 67 calculation definitions, per-driver/per-rival/session values, saved private calibration contexts, optional explicit source enrichment and a zero/one/two-stop scenario search. It preserves existing ingestion, normalization, session, feature-metric, decision and delivery boundaries. No AI model is used.

[Final health and cleanup](strategy-health-final.json) records migration head `g3d048c5b167`, one ready worker, no queued/running jobs, no temporary test schemas and no remaining temporary private strategy contexts/cache rows.

## Automated checks

**66 backend tests passed** in the complete local suite, including 27 strategy tests. Both browser workflows passed with no runtime errors. `alembic check`, dependency checks and compilation passed. The fresh-install migration test covers upgrade to the new head, schema alignment, downgrade and upgrade, including the existing one-time weather repair. Source mapping was separately rechecked after separating ingestion transport from strategy-context normalization.

Strategy tests include:

- independent matching-line gap, robust closing-rate, catch-time and simultaneous-distance ground truths;
- unchanged historical results after poisoning future speed, positions, lap outcomes, tyre age/compound and pit timestamps;
- rejection of collinear tyre-age/race-lap fits and recovery of independently specified identifiable coefficients;
- wind-from versus wind-toward convention, known head/tailwind pressure ratio and absent north calibration;
- metric survey registration, wrong-scale/collinear/bad landmark rejection, nonuniform reference timing and finish wrap;
- stale positions and teleports not becoming retirement evidence;
- single-incidence label censoring, elapsed bins, same-incident identities and multi-car model limitations;
- overlapping SC/VSC occurrence probabilities versus the distinct sum-to-one highest-response distribution;
- exact bad-stop counterfactual, without counting a rival's already incorporated stop twice;
- one- and two-stop best cost versus independent direct lap-by-lap enumeration, no physical set reuse, supported tyre age and rule constraints;
- no pit-now plan during an existing visit, no guessed post-stop compound and no default race plan after a known finish;
- actual private context save/retrieve/evaluate/cache workflows, cross-account denial, future-known input rejection, deletion cascade and bounded sample reads;
- source downloads excluded from strategy evaluation, busy behavior and cache reuse without telemetry reads.

## Authenticated real-race workflow

[Machine-readable API benchmark](strategy-api-benchmark-miami-2025.json):

| Measurement | Result |
| --- | --- |
| Dataset | Miami 2025 race, 20 entries, midpoint event-time cutoff |
| Strategy definitions | 67 |
| Returned values | 562, including rival-specific and incident-state values |
| First calculation | 0.329 s |
| Cached repeat | 0.031 s |
| Sampled input | 7,080 car and 7,100 position records over the configured lookback |
| Search | 421 candidates evaluated; 400 feasible; best twenty returned |
| Pace attribution fit | Correctly returned `unidentifiable` rather than inventing tyre/fuel coefficients |
| Actual observed focus pit visit | 22.440 s total lane time |
| Actual reported focus service | 2.7 s stationary time |

The search test used **declared synthetic tyre curves, set inventory, net pit cost and rule assumptions**. Actual source observations and a functioning scenario workflow do not establish that the toy scenario is the true optimal race strategy. The output and benchmark flag that distinction. Temporary users, contexts and private cache rows were removed and cascading deletion was verified.

## Walk-forward rival forecast

[Complete per-target results](strategy-gap-backtest-miami-2025.json): focus car 1, rival car 4. Each prediction uses only data available by a shared completed-lap cutoff and forecasts the next shared lap's gap from recent relative pace. Future values are then used for scoring. Future green/non-pit status stratifies evaluation only.

| Targets | Count | MAE | RMSE | P90 absolute error | Unchanged-gap MAE |
| --- | --- | --- | --- | --- | --- |
| All | 52 | 1.298 s | 3.382 s | 3.518 s | 1.640 s |
| Green/non-pit | 45 | 0.386 s | 0.513 s | 0.747 s | 0.706 s |

This is observational one-step forecast validation on one pair/race. It does not validate unobserved alternative pit strategies, finishing positions, every circuit or a calibrated SC forecast. Historical source revisions also limit original-arrival-time claims. All-condition errors remain reported rather than showing only the most favorable subset.

## External inputs actually obtained

- [OpenF1 pit context](miami-2025-pit-context.json): eighteen real reports, all eighteen with separate stationary service time. Source session metadata, date/year/name and driver roster were checked; export did not modify original telemetry or the database.
- [Retrospective incident export](miami-2025-incident-history.json): five labelled observations across elapsed-time bins. This is below the thirty-incident default and does not justify a precise probability. Same-race future outcomes are excluded from earlier target decisions.
- Map candidates were attempted through two public Overpass endpoints. The DE endpoint timed out; Kumi returned 500. No verified racing boundary, recovery route or north calibration was installed. The importer and independently tested metric-landmark registration remain available for reviewed source geometry.

External enrichment is explicit and separate from evaluation/replay. Network failure therefore leaves the relevant feature unavailable and does not block replay loading or manufacture geometry or probabilities.

## Existing app regressions

The production-preview browser replay test passed full-grid selection, shared active-token renewal, complete sampled race coverage, map/cards, playback/pause, seeking to finish, source-failure handling and expired-token sign-in. Cached replay became playable in **8.79 s**; the unavailable-source error appeared in **6.50 s**. The previous empty-database/provider-disk-cache loading benchmark remains documented in [backend readiness](backend-readiness.md); strategy is outside that path.

The layout-builder browser test also passed previews, groups, drag/resize/aspect/minimum rules, persistence/save retry, factory protection/copying, edit/reload, favorites, account isolation, responsive stacking and cleanup. No frontend product flows were added by the strategy work.

## Scope before real automatic strategy advice

The engine can rank explicit supported scenarios and expose their evidence today. Real recommendations still require calibrated current-car tyre/pit models, true remaining inventory/race distance, applicable event rules and sufficient field/incident data. Full multi-car interaction, passing/traffic/dirty-air response, weather-to-lap-time effects, joint incident risk and future SC duration are not declared solved. No missing input is silently replaced by a plausible-looking probability or coefficient.

See [strategy methods and extension runbook](../architecture/10-strategy-foundation.md), [calculation catalogue](../architecture/strategy-metric-catalog.md), and the executable `backend/scripts/benchmark_strategy.py` and `backtest_strategy_gaps.py` reproductions.
