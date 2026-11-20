# PitWall Insights handoff

Checkpoint from 2026-11-20 on `main`. The app is a local full-stack prototype for historical F1 analysis, with OpenF1 as its active source. [Fresh-machine setup](setup.md)

## Start here on a new machine

1. Clone the repository and open its root in VS Code. The root `AGENTS.md` points new Codex sessions to this page.
2. Install Python 3.12, Node.js 24 and Docker with Compose. Follow the [setup tutorial](setup.md) to start PostgreSQL, the API, the worker and Vite, then verify the running services.
3. Sign in as a local administrator or register a member with [email verification or Google](setup.md#enable-optional-integrations). Open **Sessions**, import an archived Grand Prix such as the 2025 Emilia Romagna GP, choose **Replay Focus**, and select drivers. Wait for the required telemetry before starting Replay. With Analyst or Pro, use **Race strategy** to check the 2025 Australian and Bahrain GPs.
4. The database, downloaded telemetry, app accounts, favorites and user layouts are local state. A new checkout re-imports public race data. Transfer a private database backup separately when you need the same accounts or custom layouts.

## Implemented paths

| Area | What works | Where to start |
| --- | --- | --- |
| Historical data | Catalog, core import, selective car and position telemetry, background worker, source cache and stored readiness | [Data flow](architecture/04-data-flow.md), [Replay loading](architecture/08-replay-loading.md), [Provider decision](architecture/11-hybrid-data-and-accounts.md) |
| Replay and session review | Shared replay clock, map and pit lane, team radio, driver cards, qualifying and practice review, full-field timing tower | [Session review](architecture/13-session-review.md), [Timing tower test](testing/timing-tower/results.json) |
| Layouts | Built-in layouts with session and mode restrictions, profile-owned layouts and favorites, resizable panels and previews | [Builder architecture](architecture/07-dashboard-builder-foundation.md), [Widget runbook](architecture/widget-creation-runbook.md) |
| Race strategy | Grand Prix Replay strategy, tyre usage, rival scenarios, forecast probability and pit loss, sector-based weather crossover | [Strategy specification](architecture/10-strategy-foundation.md), [Validation and real races](testing/replay-strategy/README.md) |
| Subscriptions | Free, Analyst and Pro access policy, layout quotas, Stripe Sandbox checkout, cancellation and webhook handling | [Design and sandbox setup](architecture/14-subscriptions.md) |
| Accounts | Password signup with email verification, Google sign-in and profile linking, local administrator provisioning and role-gated diagnostics | [Account module](modules/identity-auth.md), [Provider setup](setup.md#enable-optional-integrations) |
| Thesis | Hungarian Markdown, HTML, Word and PDF working drafts, with diagrams and actual browser captures | [Draft source](PitWall-Insights-szakdolgozat-munkavaltozat.md), [Editorial notes](PitWall-Insights-szakdolgozat-szerkesztesi-jegyzet.md) |

The last full thesis export is 42 pages before the 12-page appendix, which leaves eight pages under the 50-page cap. The Markdown draft includes the later subscription work and is the editing source. The separate subscription design document has its own UML diagrams and PDF. [Full thesis PDF](PitWall-Insights-szakdolgozat-munkavaltozat.pdf) · [Export validation](testing/thesis-draft-validation.json) · [Subscription design PDF](PitWall-Insights-elofizetes-fejlesztoi-dokumentacio.pdf)

## Next session: verify email and Google sign-in with real accounts

The account and billing code ships in this checkpoint. Automated tests use provider fixtures. Sending a real verification email, completing a Google sign-in and completing hosted Stripe Sandbox checkout are still pending.

1. Follow the [fresh-machine setup](setup.md) and apply the current migrations. Provision an administrator using the [local CLI](setup.md#local-administrator) if you need diagnostics. The role is stored in the database, so a fresh clone needs a new account or a private backup.
2. Configure a sending mailbox in the ignored `backend/.env`, then restart the API. Gmail SMTP uses an app password and STARTTLS on port 587. Open **Sign up** with a test mailbox you can read, enter the six-digit code, then sign out and verify password login. A non-Gmail recipient also tests cross-provider delivery. [Email verification setup](setup.md#email-verification)
3. Create or reuse the project's Google OAuth Web client, register the exact frontend origin, and set `GOOGLE_CLIENT_ID` in the same local env file. Restart the API, then use **Continue with Google** in a signed-out browser. Verify that a returning Google user reaches the same account and that a verified password user can link Google under **Profile → Sign-in methods**. Use separate test accounts for the direct signup and linking checks. [Google sign-in setup](setup.md#google-sign-in)
4. Sign in as both a member and an administrator. Check that the administrator can open **Admin** and read module diagnostics, and that a member receives HTTP 403 from `GET /api/auth/health`. Record observed outcomes and any provider error without publishing mailbox addresses, tokens, codes or credentials.

## Limits that matter when continuing

- As-of calculations use stored event timestamps and earlier completed sessions. Historical OpenF1 revisions lack an original arrival-time log. Preserve as-of behavior on seeks and rewinds.
- Strategy outputs are conditional estimates. Tyre inventory, wheel speeds and independent radar are unavailable. Rain scenarios need supplied forecasts. The model consumes observed sector timing and circuit-wide rainfall. Scope restrictions differ by session type.
- The documented 180-second startup target refers to full-grid preparation on the active provider. The comparable source-cache measurements in the thesis cover three drivers. A full-grid benchmark under those same conditions is open.
- Full-grid timing and strategy checks are recorded in the browser reports. This checkpoint passed 221 backend tests and 66 frontend tests, plus frontend lint and build. Treat these as dated results and rerun targeted tests after changes.

## Pending product work

1. Complete the account-provider tests above, then run hosted Stripe checkout in the project's Sandbox. Before a live payment launch, complete withdrawal, tax, invoicing and privacy obligations for the intended markets. [Subscription design](architecture/14-subscriptions.md)
2. Add the AI summary and driver comparison using existing calculations with links back to laps, sectors and values. Apply the selected replay cutoff to the context.
3. Add session Q&A and optional replay lap summaries. Natural-language catalog search can follow later.
4. Replace homepage placeholder content, implement automatically updated championship standings and a source-linked news feed. Provisional in-race standings and AI news summaries are optional follow-ups.

## Verification and thesis build

Run `npm.cmd test`, `npm.cmd run lint` and `npm.cmd run build` from `frontend`. With the local PostgreSQL instance running, run `.\.venv\Scripts\python.exe -m unittest discover -s tests -q` from `backend`. Many backend tests use temporary schemas. Browser workflows use Python Playwright with Chromium. From the root, run `python scripts/check_timing_tower.py`, `python scripts/check_replay_strategy.py` or `python scripts/check_weather_crossover.py` against the local services. Set `PITWALL_TEST_WEB=http://localhost:5173` for Vite and `PITWALL_TEST_API=http://127.0.0.1:8000` for the API.

For the thesis, use Windows with Word and install `python-docx`, `PyMuPDF` and `Pillow`. Copy the institutional `DiplomatervSablon*.docx` template from private storage into `docs/` before running `python -X utf8 docs/tools/build_thesis_draft.py --update-outline`, then `python -X utf8 docs/tools/check_thesis_draft.py`. The published task sheet has the student identifier redacted. The existing figure files are build inputs. Regenerating the flowcharts and crops uses `build_thesis_current_figures.py` with the path to Mermaid's `dist` folder and requires Playwright Chromium. `scripts/capture_thesis_appendix.py` records the editor and race updates using a temporary account and the imported 2025 Imola race. Keep signed copies, filled institutional templates and submission archives in private storage.
