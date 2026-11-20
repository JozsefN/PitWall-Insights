# PitWall-Insights
A Motorsport Telemetry and Race Strategy Analysis System

Use the [handoff](docs/handoff.md) to resume work on a new machine or in a new Codex session. It links the current architecture, tests, thesis and open tasks.

Follow the [fresh-machine setup tutorial](docs/setup.md) for startup, smoke checks, and optional Stripe and Google configuration.

## Local startup on Windows

Install Python 3.12, Node.js 24 and Docker with Compose. Open a terminal in the repository root and create the backend environment:

```powershell
py -3.12 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

Start the local API, PostgreSQL and background import/telemetry worker together from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

This command applies migrations. Ctrl+C stops the worker started by this command. Worker logs are in `%TEMP%\pitwall-worker` and the API is on port 8000 by default.

After updating this checkout, install the updated backend requirements (`cd backend; .\.venv\Scripts\python.exe -m pip install -r requirements.txt`) before starting it. OpenF1 provides the calendar and historical session data from 2023 onwards.

The [data-source decision history and final architecture](docs/architecture/11-hybrid-data-and-accounts.md) explain how the application reached its OpenF1 data path. Open `/profile` to edit account details and inspect available data. Historical replay uses the same stored data as the analysis tools. Live streaming is a separate, unfinished feature.

No external account, data-source subscription or browser extension is required for historical sessions. Set a strong `PITWALL_AUTH_SECRET` for a deployed application and use HTTPS for account authentication.

Free accounts can use full historical Replay and Lookback. Analyst and Pro add advanced analyses and higher layout quotas. Open **Profile → Subscription** to compare plans. [Stripe Sandbox and Google setup](docs/architecture/14-subscriptions.md)

Start the frontend in a second terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://localhost:5173` and sign in with a verified account or a locally provisioned administrator. See the [setup tutorial](docs/setup.md#email-verification) for Gmail SMTP, Google sign-in, and first-run account provisioning. To point Vite at another API, set `VITE_API_BASE_URL` in your ignored `frontend/.env` file.

Replay architecture, startup measurements and the current upstream archive limitation: [replay loading](docs/architecture/08-replay-loading.md).

Backend verification and timing evidence: [readiness report](docs/testing/backend-readiness.md). The existing `feature_metrics` module now exposes [137 F1 calculations and point-in-time car state](docs/architecture/09-f1-analytics.md), with a [metric catalogue](docs/architecture/f1-metric-catalog.md) and an extension runbook.

Strategy development starts with the [67 strategy primitives](docs/architecture/strategy-metric-catalog.md) and [strategy methods/runbook](docs/architecture/10-strategy-foundation.md): causal decision snapshots, rival gaps, pit counterfactuals, tyre/rule-constrained scenario search, incident calibration and wind physics. [Strategy validation](docs/testing/strategy-validation.md) records numerical tests, real-data inputs, timing and walk-forward forecast error.
