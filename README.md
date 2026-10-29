# PitWall-Insights
A Motorsport Telemetry and Race Strategy Analysis System

Start the local API, PostgreSQL and background import/telemetry worker together from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

The backend virtual environment and Docker must already be installed. This command applies migrations; Ctrl+C stops the worker started by this command. Worker logs are in `%TEMP%\pitwall-worker`.

Start the frontend in a second terminal:

```powershell
cd frontend
npm.cmd run dev
```

Replay architecture, startup measurements and the current upstream archive limitation: [replay loading](docs/architecture/08-replay-loading.md).

Backend verification and timing evidence: [readiness report](docs/testing/backend-readiness.md). The existing `feature_metrics` module now exposes [137 F1 calculations and point-in-time car state](docs/architecture/09-f1-analytics.md), with a [metric catalogue](docs/architecture/f1-metric-catalog.md) and an extension runbook.

Strategy development starts with the [67 strategy primitives](docs/architecture/strategy-metric-catalog.md) and [strategy methods/runbook](docs/architecture/10-strategy-foundation.md): causal decision snapshots, rival gaps, pit counterfactuals, tyre/rule-constrained scenario search, incident calibration and wind physics. [Strategy validation](docs/testing/strategy-validation.md) records numerical tests, real-data inputs, timing and walk-forward forecast error.
