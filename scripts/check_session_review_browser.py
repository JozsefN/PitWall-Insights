"""Exercise the review panels with real OpenF1 sessions and a temporary profile."""
from local_test_accounts import seed_verified_account
from filter_controls import select_control

import json
import os
import secrets
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs/testing/session-review-browser"
BASE = os.environ.get("PITWALL_TEST_WEB", "http://127.0.0.1:4173")
API = os.environ.get("PITWALL_TEST_API", "http://127.0.0.1:8000")


def api(method, path, token=None, payload=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None if payload is None else json.dumps(payload).encode()
    with urlopen(
        Request(API + path, method=method, data=body, headers=headers), timeout=90
    ) as response:
        return json.load(response)


def seed_test_membership(owner, prefix):
    """Give a temporary browser-test account access to advanced panels."""
    script = """
from datetime import datetime, timedelta, timezone
import sys
from modules.billing.infrastructure.db_models import BillingAccountRecord
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.storage.infrastructure.db import SessionLocal
with SessionLocal() as db:
    user = db.get(UserRecord, sys.argv[1])
    assert user and user.email.startswith(sys.argv[2]) and user.email.endswith('@example.com')
    db.add(BillingAccountRecord(user_id=user.id, plan_code='pro', status='active',
                                paid_until=datetime.now(timezone.utc) + timedelta(hours=1)))
    db.commit()
"""
    subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", script, owner, prefix],
                   cwd=ROOT / "backend", check=True)


def capture(locator, filename):
    locator.evaluate("node => node.scrollIntoView({block: 'center', inline: 'nearest'})")
    locator.screenshot(path=str(ARTIFACTS / filename))


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    email = f"review-e2e-{secrets.token_hex(6)}@example.com"
    password = secrets.token_urlsafe(20)
    token = seed_verified_account({"email": email, "password": password})["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    report = {}
    try:
        seed_test_membership(owner, "review-e2e-")
        sources = [(1, "Qualifying"), (4, "Race"), (4, "Practice 2")]
        catalogue = api("GET", "/api/sessions/catalog?season=2025", token)
        sessions = {}
        for round_no, name in sources:
            key = next(
                (
                    row["source_session_key"]
                    for row in catalogue
                    if row["round_number"] == round_no and row["session_name"] == name
                ),
            )
            row = api(
                "POST",
                "/api/sessions/import",
                token,
                {
                    "season_year": 2025,
                    "round_number": round_no,
                    "session_name": name,
                    "source_session_key": key,
                    "import_profile": "core",
                },
            )
            sessions[name] = row["id"]
        quali = api(
            "POST",
            f"/api/feature-metrics/sessions/{sessions['Qualifying']}/review",
            token,
            {"groups": ["drivers", "radio"]},
        )["groups"]
        assert len(quali["radio"]["clips"]) > 0
        assert len([card for card in quali["drivers"] if card["headshot_url"]]) >= 15
        assert sum(bool(card["qualifying"]) for card in quali["drivers"]) >= 15
        report["qualifying_radio_clips"] = len(quali["radio"]["clips"])
        report["qualifying_phase_counts"] = [
            sum(
                any(row["phase"] == n for row in card["qualifying"])
                for card in quali["drivers"]
            )
            for n in (1, 2, 3)
        ]
        sid = sessions["Race"]
        race = api(
            "POST",
            f"/api/feature-metrics/sessions/{sid}/review",
            token,
            {"groups": ["pit", "pace", "racecraft"], "as_of_ms": 10300000},
        )["groups"]
        net = race["pit"]["net_green_pit_loss"]
        assert net["sample_count"] >= 3 and 10 < net["median_s"] < 40, net
        assert race["pit"]["exit_scenarios"]
        assert race["pace"]["practice_profiles"]
        report["bahrain_net_pit_loss"] = {
            key: net[key] for key in ("sample_count", "median_s", "robust_scatter_s")
        }
        report["bahrain_practice_compounds"] = [
            row["compound"] for row in race["pace"]["practice_profiles"]
        ]
        stored = next(
            row["id"]
            for row in api("GET", "/api/sessions", token)
            if row["source_session_key"] == "openf1:session:9693"
        )
        cards = api(
            "POST",
            f"/api/feature-metrics/sessions/{stored}/review",
            token,
            {"groups": ["drivers"]},
        )["groups"]["drivers"]
        choices = [
            {"entry_id": card["entry_id"], "lap_number": card["best_clean_lap_number"]}
            for card in cards
            if card["car_number"] in ("1", "4", "16")
        ]
        segments = api(
            "POST",
            f"/api/feature-metrics/sessions/{stored}/review",
            token,
            {"groups": ["segments"], "laps": choices},
        )["groups"]["segments"]
        assert segments["supported"] == 3
        report["australia_supported_segment_laps"] = segments["supported"]
        layout = api("POST", "/api/layouts", token, {
            "name": "Segment comparison",
            "audience": "session-lookback",
            "schemaVersion": 2,
            "config": {"id": "segment-comparison", "sections": [{
                "id": "main",
                "layout": {"type": "group", "direction": "row", "gap": 12,
                    "grid": {"columns": 12, "rowHeight": 48}, "children": [{
                        "type": "widget", "widgetId": "lap-segment-review", "instanceId": "segments",
                        "placement": {"x": 0, "y": 0, "w": 6, "h": 8},
                    }]},
            }]},
        })
        errors = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.set_default_timeout(15000)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/login")
            page.get_by_label("Email", exact=True).fill(email)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.locator(".app-header").get_by_role(
                "button", name="Sign out", exact=True
            ).wait_for()
            page.goto(
                BASE
                + f"/sessions/{sessions['Qualifying']}?mode=lookback&layout=builtin:qualifying-review"
            )
            cards_panel = page.locator('[data-review-panel="lookback-driver-cards"]')
            expect(cards_panel.locator(".review-phase").first).to_be_visible()
            expect(
                cards_panel.locator(".review-driver-identity img").first
            ).to_be_attached()
            expect(page.locator(".team-radio-list__play").first).to_be_attached()
            page.locator(
                '[data-review-panel="lookback-driver-cards"]'
            ).scroll_into_view_if_needed()
            page.screenshot(path=str(ARTIFACTS / "qualifying.png"))
            for session, mode, layout_id, message in (
                (stored, "lookback", "qualifying-review", "Qualifying only"),
                (sessions["Practice 2"], "simulation", "qualifying-review", "Lookback only"),
                (sessions["Practice 2"], "simulation", "engineering-desk", "Grand Prix only"),
            ):
                page.goto(BASE + f"/sessions/{session}?mode={mode}&layout=builtin:{layout_id}")
                expect(page.locator(".layout-availability-message")).to_contain_text(message)
                expect(page.locator(".responsive-widget")).to_have_count(0)
            page.goto(
                BASE
                + f"/sessions/{stored}?mode=lookback&layout=user:{layout['id']}&drivers={','.join(row['entry_id'] for row in choices)}"
            )
            expect(page.locator(".review-segment-grid").first).to_be_attached()
            expect(
                page.locator(".review-segment-grid").first.locator("details")
            ).to_have_count(20)
            page.goto(
                BASE
                + f"/sessions/{sid}?mode=simulation&layout=builtin:race-strategy-review"
            )
            slider = page.locator(".sessions-replay-timeline input[type=range]")
            slider.wait_for()
            page.wait_for_function("document.querySelector('.sessions-replay-timeline input').max > 10300000")
            start_ms = int(slider.get_attribute("min"))

            def elapsed(cutoff):
                minutes, seconds = divmod(max(0, (cutoff - start_ms) // 1000), 60)
                hours, minutes = divmod(minutes, 60)
                return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"

            def seek(value):
                slider.evaluate(
                    """(node,value)=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(node,String(value));node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));}""",
                    value,
                )

            seek(10300000)
            expect(
                page.get_by_text("Projection after 5 laps", exact=True)
            ).to_be_attached()
            horizon = page.get_by_label("Projection horizon", exact=True)
            forecast = page.locator('[data-review-panel="race-pace-forecast"]')
            status = forecast.locator(".insight-context")
            gap_chart = forecast.locator(".field-projection")
            expect(gap_chart.locator(".strategy-timing-row")).to_have_count(
                sum("projected_gap_s" in row for row in race["pace"]["field_projection"]), timeout=30000,
            )
            gap_picker = gap_chart.get_by_label("Focus projected driver")
            frame = page.locator('[data-widget="race-pace-forecast"]')
            chart_size = frame.bounding_box()["height"]
            select_control(gap_picker, index=2)
            expect(gap_chart.locator(".strategy-timing-row")).to_have_count(1)
            expect(gap_chart.locator('[data-highlight="true"]')).to_contain_text("P2")
            capture(gap_chart, "projected-gap.png")
            select_control(gap_picker, "")
            assert frame.bounding_box()["height"] == chart_size
            expect(forecast.locator(".race-pace-chart .strategy-timing-row")).to_have_count(len(race["pace"]["drivers"]))
            forecast.get_by_text("Pace times and evidence", exact=True).click()
            expect(forecast.get_by_role("table")).to_be_visible()
            forecast.get_by_text("Pace times and evidence", exact=True).click()
            pit = page.locator('[data-review-panel="pit-benchmark"]')
            expect(pit.locator(".pit-timing-profile .strategy-timing-track").first).to_be_attached()
            expect(pit.locator(".pit-timing-profile")).to_contain_text(f"{net['median_s']:.2f} s")
            rejoin = pit.locator(".pit-rejoin-visual")
            scenario = race["pit"]["exit_scenarios"][-1]
            select_control(rejoin.get_by_label("Pit rejoin driver"), scenario["entry_id"])
            expect(rejoin.locator(".pit-rejoin-grid li")).to_have_count(scenario["timed_entries"])
            expect(rejoin.locator('[data-rejoin="true"]')).to_have_text(str(scenario["exit_order_among_timed_entries"]))
            capture(rejoin, "pit-rejoin.png")
            capture(pit.locator(".pit-timing-profile"), "pit-timing.png")
            racecraft = page.locator('[data-review-panel="racecraft-review"]')
            active = [row for row in race["racecraft"]["battles"] if row["active_battle"] or row["consistent_closing"]]
            expect(racecraft.locator(".battle-gaps .pit-timing-row")).to_have_count(len(active))
            if active:
                gap = min(row["gap_s"] for row in active)
                expect(racecraft.locator(".battle-gaps .pit-timing-row").first).to_contain_text(f"{gap:.2f} s")
                capture(racecraft.locator(".battle-gaps"), "battle-gaps.png")
            if race["pit"]["rival_windows"]:
                margins = pit.locator(".pit-rival-margins")
                pit.get_by_text("Rival pit opportunities", exact=False).click()
                expect(margins.locator(".pit-timing-row")).to_have_count(min(10, len(race["pit"]["rival_windows"])))
                expect(margins.locator(".strategy-timing-track em").first).to_be_visible()
                pit.get_by_text("Rival pit opportunities", exact=False).click()
            report["bahrain_timing_visuals"] = {
                "projected_drivers": sum("projected_gap_s" in row for row in race["pace"]["field_projection"]),
                "rejoin_scenarios": len(race["pit"]["exit_scenarios"]),
                "active_or_closing_pairs": len(active),
                "rival_pit_windows": len(race["pit"]["rival_windows"]),
            }
            projection = page.get_by_text("Projection after 10 laps", exact=True)
            pending = []
            blocked_cutoff = None
            block_horizon = True

            def delay_review(route):
                body = route.request.post_data_json or {}
                is_blocked_cutoff = (
                    blocked_cutoff is not None and body.get("as_of_ms") == blocked_cutoff
                )
                if is_blocked_cutoff or (block_horizon and body.get("horizon_laps") == 10):
                    pending.append(route)
                else:
                    route.continue_()

            page.route("**/review", delay_review)
            select_control(horizon, "10")
            expect(status).to_contain_text("Updating · Default shown")
            expect(page.get_by_text("Projection after 5 laps", exact=True)).to_be_attached()
            block_horizon = False
            for request in pending:
                request.continue_()
            pending.clear()
            expect(
                page.get_by_text("Projection after 10 laps", exact=True)
            ).to_be_attached()
            page.get_by_label("Fuel scenario", exact=True).check()
            expect(
                page.get_by_text("Fuel scenario reduces", exact=False)
            ).to_be_attached()
            page.locator(
                '[data-review-panel="pit-benchmark"]'
            ).scroll_into_view_if_needed()
            page.screenshot(path=str(ARTIFACTS / "race-strategy.png"))
            dashboard = page.locator(".sessions-workspace__stage .dashboard")
            start = page.get_by_role("button", name="Start", exact=True)
            replay_status = page.locator("#replay-start-status")

            def panel_heights():
                return tuple(node.evaluate("node => node.offsetHeight") for node in (dashboard, frame))

            for width, cutoff, prior in (
                (1440, 10305000, 10300000),
                (390, 10310000, 10305000),
            ):
                page.set_viewport_size({"width": width, "height": 844})
                sizes = panel_heights()
                blocked_cutoff = cutoff
                seek(cutoff)
                expect(status.locator('[data-visible="true"]')).to_have_text("Updating")
                expect(status).to_contain_text(elapsed(prior))
                expect(projection).to_be_attached()
                expect(start).to_be_disabled()
                expect(replay_status).to_contain_text("Loading the session review")
                assert sizes == panel_heights()
                assert pending
                blocked_cutoff = None
                for request in pending:
                    request.continue_()
                pending.clear()
                expect(status).to_contain_text(elapsed(cutoff))
                expect(start).to_be_enabled()
                assert sizes == panel_heights()
                if width == 390:
                    select_control(gap_picker, index=1)
                    capture(gap_chart, "projected-gap-mobile.png")
                    select_control(gap_picker, "")

            blocked_cutoff = 10295000
            seek(blocked_cutoff)
            expect(projection).to_have_count(0)
            expect(status).not_to_contain_text(elapsed(10310000))
            expect(horizon).to_have_value("10")
            assert sizes == panel_heights()
            blocked_cutoff = None
            for request in pending:
                request.continue_()
            pending.clear()
            expect(status).to_contain_text(elapsed(10295000))
            expect(projection).to_be_attached()
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            )

            # The real Bahrain snapshot above has no position flip. Exercise the
            # presentation with a controlled rival-stop comparison at a new cutoff.
            synthetic_cutoff = 10315000

            def add_rival_window(route):
                body = route.request.post_data_json or {}
                if body.get("as_of_ms") != synthetic_cutoff or "pit" not in body.get("groups", []):
                    route.fallback()
                    return
                response = route.fetch()
                if not response.ok:
                    route.fulfill(response=response)
                    return
                snapshot = response.json()
                first, second = race["pit"]["exit_scenarios"][:2]
                snapshot["groups"]["pit"]["rival_windows"] = [{
                    "entry_id": first["entry_id"],
                    "rival_entry_id": second["entry_id"],
                    "rival_stop_excess_s": 2.0,
                    "exit_margin_s": 0.7,
                    "normal_rival_stop_margin_s": -1.3,
                    "position_flip_scenario": True,
                }]
                route.fulfill(response=response, json=snapshot)

            page.route("**/review", add_rival_window)
            seek(synthetic_cutoff)
            pit.get_by_text("Rival pit opportunities", exact=False).click(timeout=30000)
            margins = pit.locator(".pit-rival-margins")
            expect(margins).to_contain_text("Reported rival stop 0.70 s ahead")
            expect(margins).to_contain_text("Typical rival stop 1.30 s behind")
            track = margins.locator(".strategy-timing-track")
            reported, typical = track.evaluate("""node => ['--timing-point', '--timing-normal']
                .map(key => Number.parseFloat(node.style.getPropertyValue(key)))""")
            assert typical < 50 < reported, (typical, reported)
            capture(margins, "rival-pit-margin-example.png")
            assert not errors, errors
            browser.close()
        report["browser_checks"] = [
            "qualifying cards and in-panel radio playback control",
            "qualifying-only and Grand Prix-only layouts blocked outside supported sessions",
            "real lap segment comparison",
            "replay projection horizon and fuel scenario",
            "field projection focus, pace evidence, pit rejoin selection, timed benchmarks and active battle rows",
            "rival-stop position flip visual with controlled comparison data",
            "strategy data and panel heights stay stable during delayed refresh on desktop and mobile",
            "rewind excludes future strategy values and preserves scenario controls",
            "strategy replay waits for its review snapshot without requiring raw telemetry",
            "mobile viewport and no runtime errors",
        ]
        report["errors"] = errors
        (ARTIFACTS / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
    finally:
        code = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
 user=db.get(UserRecord,sys.argv[1])
 if user and user.email.startswith('review-e2e-'):
  db.delete(user)
  db.commit()
"""
        subprocess.run(
            [str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", code, owner],
            cwd=ROOT / "backend",
            check=True,
        )


if __name__ == "__main__":
    main()
