# Historical replay loading

The current data path uses OpenF1 for both calendar discovery and historical data.
The user selects a session and lookback or replay mode, without selecting a provider
or connecting an external account.

## Startup path

1. Import core data: roster, laps, stints, flags, weather and available source reports.
2. Persist a canonical snapshot and open the session workspace.
3. Determine which selected drivers and telemetry kinds the layout requires.
4. Reuse completed materialized segments; queue only missing segments.
5. The worker loads selected OpenF1 telemetry, normalizes it and writes bounded batches.
6. The frontend polls readiness, reads a compact timeline and samples the full replay duration.

The replay clock is independent of raw tick-row count. Requests cover the whole
session, including its exact final time, rather than taking only the first page
of high-rate measurements. Playback, seeking and speed controls use a shared time.
Authentication renewal for the PitWall account prevents long-running workspaces
from failing solely because the application's access token expired.

## Failure handling

Upcoming or cancelled sessions show an availability reason. Historical coverage
can still be incomplete. Failed telemetry is not a successful empty cache, and
unknown observations are not converted to valid measurements. Source messages
are retained in actionable import errors. A stopped worker and a source outage
are separate operational conditions.

## Evidence and limitations

Earlier replay benchmarks belong to their recorded program versions and cache
conditions. The 93.687-second field-wide measurement is a historical implementation
baseline; it is not a new OpenF1 download benchmark. Earlier OpenF1 three-driver
measurements recorded 52.487 seconds initially and 16.820 seconds with a warm source
cache. They do not establish a startup SLA for every race or the full grid.

The thesis chapter 4.8 documents the original source, the intermediate hybrid plan,
and the final OpenF1 architecture. The current selected test scope is 2023-2025.
Live streaming is a separate, unfinished data workflow.
