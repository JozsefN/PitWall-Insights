# PitWall Insights handoff

Checkpoint from 2026-11-20 on `main`. The app is a local full-stack prototype for historical F1 analysis, with OpenF1 as its active source. [Local setup](../README.md)

## Start here on a new machine

1. Clone the repository and open its root in VS Code. The root `AGENTS.md` points new Codex sessions to this page.
2. Install Python 3.12, Node.js 24 and Docker with Compose. Follow the Windows startup steps in the README to start PostgreSQL, migrate it, launch the API and start the separate worker. Run Vite in another terminal.
3. Register a new local app account. Open **Sessions**, import an archived Grand Prix such as the 2025 Emilia Romagna GP, choose **Replay Focus** or **Race strategy**, and select drivers. Wait for the required telemetry before starting Replay. The 2025 Australian and Bahrain GPs are useful for weather and strategy checks.
4. The database, downloaded telemetry, app accounts, favorites and user layouts are local state. A new checkout re-imports public race data. Transfer a private database backup separately when you need the same accounts or custom layouts.

## Implemented paths

| Area | What works | Where to start |
| --- | --- | --- |
| Historical data | Catalog, core import, selective car and position telemetry, background worker, source cache and stored readiness | [Data flow](architecture/04-data-flow.md), [Replay loading](architecture/08-replay-loading.md), [Provider decision](architecture/11-hybrid-data-and-accounts.md) |
| Replay and session review | Shared replay clock, map and pit lane, team radio, driver cards, qualifying and practice review, full-field timing tower | [Session review](architecture/13-session-review.md), [Timing tower test](testing/timing-tower/results.json) |
| Layouts | Built-in layouts with session and mode restrictions, profile-owned layouts and favorites, resizable panels and previews | [Builder architecture](architecture/07-dashboard-builder-foundation.md), [Widget runbook](architecture/widget-creation-runbook.md) |
| Race strategy | Grand Prix Replay strategy, tyre usage, rival scenarios, forecast probability and pit loss, sector-based weather crossover | [Strategy specification](architecture/10-strategy-foundation.md), [Validation and real races](testing/replay-strategy/README.md) |
| Thesis | Hungarian Markdown, HTML, Word and PDF working drafts, with diagrams and actual browser captures | [Draft source](PitWall-Insights-szakdolgozat-munkavaltozat.md), [Editorial notes](PitWall-Insights-szakdolgozat-szerkesztesi-jegyzet.md) |

The last thesis export is 42 pages before the 12-page appendix, which leaves eight pages under the 50-page cap. The appendix contains the builder, race and qualifying views, close-up and full-grid maps, race updates and extra diagrams. Section 2.3 covers the technology choices, 5.2 covers replay, 5.4 covers strategy and 8.2 records the original plan as pending work. Use the Markdown as the editing source. [PDF](PitWall-Insights-szakdolgozat-munkavaltozat.pdf) · [Export validation](testing/thesis-draft-validation.json)

## Limits that matter when continuing

- As-of calculations use stored event timestamps and earlier completed sessions. Historical OpenF1 revisions lack an original arrival-time log. Preserve as-of behavior on seeks and rewinds.
- Strategy outputs are conditional estimates. Tyre inventory, wheel speeds and independent radar are unavailable. Rain scenarios need supplied forecasts. The model consumes observed sector timing and circuit-wide rainfall. Scope restrictions differ by session type.
- The documented 180-second startup target refers to full-grid preparation on the active provider. The comparable source-cache measurements in the thesis cover three drivers. A full-grid benchmark under those same conditions is open.
- Full-grid timing and strategy checks are recorded in the browser reports. The publication checkpoint passed 213 backend tests including the migration test and 65 frontend tests, plus frontend lint and build. Treat these as dated results and rerun targeted tests after changes.

## Pending product work

1. Implement Free, Analyst and Pro entitlements around layouts, panels and advanced analysis, with test checkout and server-side access enforcement. Pricing and quotas still need decisions.
2. Add the AI summary and driver comparison using existing calculations with links back to laps, sectors and values. Apply the selected replay cutoff to the context.
3. Add session Q&A and optional replay lap summaries. Natural-language catalog search can follow later.
4. Replace homepage placeholder content, implement automatically updated championship standings and a source-linked news feed. Provisional in-race standings and AI news summaries are optional follow-ups.

## Verification and thesis build

Run `npm.cmd test`, `npm.cmd run lint` and `npm.cmd run build` from `frontend`. With the local PostgreSQL instance running, run `.\.venv\Scripts\python.exe -m unittest discover -s tests -q` from `backend`. Many backend tests use temporary schemas. Browser workflows use Python Playwright with Chromium. From the root, run `python scripts/check_timing_tower.py`, `python scripts/check_replay_strategy.py` or `python scripts/check_weather_crossover.py` against the local services. Set `PITWALL_TEST_WEB=http://localhost:5173` for Vite and `PITWALL_TEST_API=http://127.0.0.1:8000` for the API.

For the thesis, use Windows with Word and install `python-docx`, `PyMuPDF` and `Pillow`. Copy the institutional `DiplomatervSablon*.docx` template from private storage into `docs/` before running `python -X utf8 docs/tools/build_thesis_draft.py --update-outline`, then `python -X utf8 docs/tools/check_thesis_draft.py`. The published task sheet has the student identifier redacted. The existing figure files are build inputs. Regenerating the flowcharts and crops uses `build_thesis_current_figures.py` with the path to Mermaid's `dist` folder and requires Playwright Chromium. `scripts/capture_thesis_appendix.py` records the editor and race updates using a temporary account and the imported 2025 Imola race. Keep signed copies, filled institutional templates and submission archives in private storage.
