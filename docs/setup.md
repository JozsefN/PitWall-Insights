# Set up PitWall Insights on another machine

This guide starts PostgreSQL, the API, the import and telemetry worker, and the Vite frontend. You can sign in as a locally provisioned administrator, register with an email verification code, or configure Google sign-in. Stripe Sandbox is optional for historical Replay.

## 1. Get the code and tools

Install Git, Python **3.12**, Node.js **24**, and Docker with the Compose plugin. On Windows, start Docker Desktop and use PowerShell for the Windows commands below. [Git](https://git-scm.com/install/) · [Python](https://www.python.org/downloads/) · [Node.js](https://nodejs.org/en/download) · [Docker](https://docs.docker.com/get-docker/)

```text
git clone https://github.com/JozsefN/PitWall-Insights.git
cd PitWall-Insights
git branch --show-current
git rev-parse --short HEAD
```

Use the repository root, the directory containing `backend`, `frontend`, and `shared`, as the starting point for each terminal. To reproduce someone else's checkout, ask for the branch and commit. Run `git status --short` on the source machine to see whether it also has working-copy changes. A clone contains the committed files on its branch. Transfer any required pending source changes separately and keep local `.env` files, database dumps, credentials, and private thesis inputs outside Git.

### Check the installed tools

On Windows, run `py -3.12 --version`, `node --version`, `npm.cmd --version`, `docker compose version`, and `docker info`. On macOS or Linux, use `python3.12 --version` and `npm --version`. `docker info` should show a server section, which confirms that the Docker engine is running.

## 2. Start the app on Windows

**Terminal 1 — PostgreSQL, API, and worker.** Run from the repository root.

```powershell
py -3.12 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

The [Windows startup script](../scripts/start-backend.ps1) waits for PostgreSQL, applies Alembic migrations, starts the worker, and runs Uvicorn on port 8000. Keep this terminal open. The worker started by the script writes logs to `$env:TEMP\pitwall-worker\stdout.log` and `stderr.log`. On later starts, run the startup script again. Rerun the dependency installation after changes to the requirements.

**Terminal 2 — frontend.** Start in the repository root.

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev -- --port 5173 --strictPort
```

Open **<http://localhost:5173>**. Vite uses the API at `http://localhost:8000` by default.

## 3. Start the services manually on macOS or Linux

Use three terminals and start each one in the repository root. If a compatible PostgreSQL instance is already available, give the app its database connection string in `backend/.env` and use the API and worker commands with that database.

**Terminal 1 — PostgreSQL and API.**

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
docker compose up -d --wait
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — worker.** Start it once migrations finish. The API and worker both read the settings from `backend/.env` when launched from `backend/`.

```bash
cd backend
.venv/bin/python -u -m app.worker
```

**Terminal 3 — frontend.**

```bash
cd frontend
npm ci
npm run dev -- --port 5173 --strictPort
```

The same manual startup works in PowerShell. Use `py -3.12` for `venv`, `.\.venv\Scripts\python.exe` for the Python commands, and `npm.cmd` for the frontend commands. A manually started API and worker each have their own terminal logs.

## 4. Verify the app and import a first session

1. Open <http://127.0.0.1:8000/api/health>. Look for **`db.status` equal to `connected`**. The interactive API reference is at <http://127.0.0.1:8000/docs>.
2. Sign in with an existing verified account or a locally provisioned administrator. To try ordinary registration on a fresh database, first configure [verification email](#email-verification) or [Google sign-in](#google-sign-in).
3. Open **Sessions**, pick season **2025**, and select the **Race** at the **Emilia Romagna Grand Prix**. Choose **Replay**, then **Load session**. Choose **Replay Focus** in the workspace and select two or three drivers. Wait for the relevant telemetry to finish preparing, then press **Start**. Verify that the clock advances, the map moves, and seeking changes the timing display.
4. Open **Dashboard Builder**, save a small layout, and reopen it to verify that user data persists. **Profile → Data availability** describes the OpenF1 coverage.

Historical imports need Internet access to OpenF1. A fresh checkout starts with an empty session list. The worker downloads core data first and prepares the selected drivers' telemetry as needed. If a session has gaps or an OpenF1 request fails, try a different archived session such as the 2025 Bahrain Grand Prix. [OpenF1 API](https://openf1.org/docs/) · [Replay loading and source limitations](architecture/08-replay-loading.md)

## 5. Enable optional integrations

For these features, use the branch or working copy that contains [the account and billing changes](architecture/14-subscriptions.md).

### Local administrator

From `backend/`, promote a trusted existing account while connected to the intended database. The role is stored in PostgreSQL. The account keeps its password and can sign in without an email code. System diagnostics are available from the **Admin** link.

```powershell
.\.venv\Scripts\python.exe -m scripts.promote_admin admin@admin.hu
```

For a fresh database, use the same command with `--create` and enter a strong password at the prompt. On macOS or Linux, use `.venv/bin/python`. The CLI provisions administrators locally. Public registration always creates member accounts.

### Email verification

Password signups need a six-digit code sent to the account email. Existing unverified member accounts complete the same step at their next sign-in. Codes expire after ten minutes, and retries and sends are limited. Configure a Gmail account with two-step verification and an app password, or use another authenticated SMTP provider. The sending inbox can be Gmail while the recipient uses any email provider. [Google app passwords](https://support.google.com/accounts/answer/185833) · [Gmail SMTP setup](https://support.google.com/a/answer/176600)

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<sending Gmail address>
SMTP_FROM_EMAIL=<same Gmail address>
SMTP_PASSWORD=<Gmail app password>
```

Add these to your private `backend/.env` and restart the API. Port `587` uses STARTTLS. For a provider that requires implicit TLS, set `SMTP_IMPLICIT_TLS=true` with its TLS port. Open <http://127.0.0.1:8000/api/auth/config> and check that `email_verification_available` is `true`. That confirms the API has the settings. To verify delivery, open **Sign up**, request a code for a mailbox you can read, and enter it in the browser.

### Stripe Sandbox

1. Create or select a [Stripe Sandbox](https://dashboard.stripe.com/sandboxes). Create two products with four active **recurring** HUF prices. Analyst is **1,490 Ft/month** and **14,900 Ft/year**. Pro is **2,490 Ft/month** and **24,900 Ft/year**. Copy the four `price_` IDs and the Sandbox `sk_test_` key. [Stripe product and price setup](https://docs.stripe.com/products-prices/manage-prices)
2. Install the Stripe CLI, sign in, and select the same Sandbox used for the prices. Leave the listener running and use the `whsec_` signing secret it prints. [Stripe CLI installation](https://docs.stripe.com/cli/install) · [Stripe login](https://docs.stripe.com/cli/login) · [Webhook listener](https://docs.stripe.com/cli/listen)

   ```text
   stripe login
   stripe listen --all-snapshot --forward-to http://127.0.0.1:8000/api/billing/webhook
   ```

3. Add these settings to the local `backend/.env` and restart the API. Set `WEB_APP_URL` to the exact frontend origin you open in the browser, including its hostname and port. The placeholders below represent your own Sandbox credentials and price IDs.

   ```dotenv
   WEB_APP_URL=http://localhost:5173
   STRIPE_TEST_SECRET_KEY=<Sandbox sk_test key>
   STRIPE_WEBHOOK_SECRET=<listener whsec key>
   STRIPE_ANALYST_MONTH_PRICE=<Analyst monthly price ID>
   STRIPE_ANALYST_YEAR_PRICE=<Analyst annual price ID>
   STRIPE_PRO_MONTH_PRICE=<Pro monthly price ID>
   STRIPE_PRO_YEAR_PRICE=<Pro annual price ID>
   ```

4. In **Profile → Subscription**, choose a plan and complete Stripe Checkout with `4242 4242 4242 4242`, a future expiration, a three-digit CVC, and a test billing address. After returning, check the plan or click **Refresh status**. Test **Stop renewal** and confirm that the paid plan remains available through the displayed end date. Use separate PitWall accounts to test Analyst and Pro back to back. Configure the Stripe Sandbox Customer Portal if you also want to test **Billing details & invoices**. [Stripe test cards](https://docs.stripe.com/testing) · [Customer Portal configuration](https://docs.stripe.com/customer-management/configure-portal)

### Google sign-in

1. In Google Cloud, configure the Google Auth Platform branding and audience for the app and create an OAuth client of type **Web application**. Add the exact frontend origin, such as `http://localhost:5173`, under **Authorized JavaScript origins**. [Google client setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid)
2. Set `GOOGLE_CLIENT_ID` in the ignored `backend/.env` and match `WEB_APP_URL` to the origin you use in the browser. This Google Identity Services integration uses the client ID only. Restart the API and check that <http://127.0.0.1:8000/api/auth/google/config> reports `enabled: true`.
3. Open the frontend at that same origin and use **Continue with Google** on the login or signup page. Gmail and verified Google Workspace identities can sign in directly. For a new Google identity using an external mailbox, complete the PitWall email code. To attach Google to an existing password account, sign in and use **Profile → Sign-in methods**. [Google email verification guidance](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)

## 6. Move local state or run two copies

The default PostgreSQL database `pitwall_insights` lives in a Docker volume. It contains application accounts, layouts, imported sessions, telemetry, and billing references. A fresh machine can re-import sessions and create new accounts. To transfer the existing records, run this from the repository root on the source machine. The backup destination is the parent of the repository folder.

```text
docker compose -f backend/docker-compose.yml exec -T postgres pg_dump -U postgres -Fc -f /tmp/pitwall-transfer.dump pitwall_insights
docker compose -f backend/docker-compose.yml cp postgres:/tmp/pitwall-transfer.dump ../pitwall-transfer.dump
```

Transfer the dump privately to the new machine and place it next to the cloned repository. Start PostgreSQL, then run these commands from the new repository root. Choose an unused database name if `pitwall_restored` already exists.

```text
docker compose -f backend/docker-compose.yml up -d --wait
docker compose -f backend/docker-compose.yml exec -T postgres createdb -U postgres pitwall_restored
docker compose -f backend/docker-compose.yml cp ../pitwall-transfer.dump postgres:/tmp/pitwall-transfer.dump
docker compose -f backend/docker-compose.yml exec -T postgres pg_restore -U postgres --exit-on-error --no-owner -d pitwall_restored /tmp/pitwall-transfer.dump
```

Set `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/pitwall_restored` in `backend/.env`, then start the app. The startup migration brings the restored schema up to the checked-out version. Select the original Stripe Sandbox if the records include its customers or subscriptions. Sign in again on the new machine. Local authentication automatically creates its own signing key there.

To run a **second independent app on the same machine**, reuse the existing local PostgreSQL service and create a separate database from the repository root.

```text
docker compose -f backend/docker-compose.yml exec -T postgres createdb -U postgres pitwall_second
```

In the second checkout, set `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/pitwall_second` and `WEB_APP_URL=http://localhost:5174` in `backend/.env`. Set `VITE_API_BASE_URL=http://localhost:8001` in `frontend/.env`. Follow the manual startup commands, reusing PostgreSQL and starting Uvicorn on `8001` and Vite on `5174`. Give the second worker the second checkout's database settings. If you test Stripe there, forward its signing listener to port `8001` and use the second frontend origin.

To stop a local app, press **Ctrl+C** in the application terminals. If no other local instance uses the database, `docker compose -f backend/docker-compose.yml stop` stops PostgreSQL while preserving the volume.

## 7. Troubleshoot startup

| Symptom | What to check |
| --- | --- |
| Docker cannot connect | Open Docker Desktop or start the Docker Engine, then retry `docker info`. |
| A port is occupied | The defaults are PostgreSQL `5432`, API `8000`, and Vite `5173`. Use the running stack or follow the second-instance steps for separate app ports and data. |
| API loads but reports a disconnected database | Check `docker compose -f backend/docker-compose.yml ps` and the API's `DATABASE_URL`. Apply migrations from `backend/` after PostgreSQL is healthy. |
| Browser requests go to the wrong API or fail CORS | Match `frontend/.env`'s `VITE_API_BASE_URL` to the API address and `backend/.env`'s `WEB_APP_URL` to the browser's frontend origin. Restart the affected process after editing an env file. |
| Import or telemetry stays queued | Check the worker terminal or the Windows worker logs. Confirm the worker and API use the same database. A healthy API alone establishes connectivity to PostgreSQL. Queue movement or a recent worker heartbeat verifies the worker. |
| Verification emails do not arrive | Check the email configuration endpoint, then check the API log for SMTP failures. Confirm the sender and app password have access to the configured SMTP service and check the test recipient's spam folder. |
| Google sign-in is unavailable | Check the Google configuration endpoint. If it is enabled, confirm that Google allows the exact origin displayed in the browser and that the test account is allowed by the OAuth audience. |
| Plan buttons are disabled | On a Free account, check that the Sandbox key, webhook secret, and four distinct Price IDs are present in `backend/.env`. Restart the API and reload the profile. |

For a command-line worker check on the default local database, run this from the repository root. A running worker writes a heartbeat every ten seconds.

```text
docker compose -f backend/docker-compose.yml exec -T postgres psql -U postgres -d pitwall_insights -c "select count(*) as active_workers from telemetry_worker_heartbeats where heartbeat_at > now() - interval '30 seconds';"
```

## Handoff prompt for another AI

> Read `AGENTS.md`, `docs/setup.md`, and `docs/handoff.md`. Start PostgreSQL, apply migrations, and launch the API, worker, and frontend. Use the account checklist in the handoff to configure and test real verification email and Google sign-in. Report which checks passed, the URLs in use, and any blocker. Keep credentials, database dumps, and private documents outside Git.
