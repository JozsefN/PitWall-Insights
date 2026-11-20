"""Check the strategy endpoint and the race strategy layout with stored OpenF1 races."""
from local_test_accounts import seed_verified_account

import json
import re
import secrets
import subprocess
from time import monotonic
from urllib.error import HTTPError
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright
from check_session_review_browser import BASE, ROOT, api, seed_test_membership

ARTIFACTS = ROOT / "docs/testing/replay-strategy"


def capture(panel, name):
    panel.evaluate("node => node.scrollIntoView({block: 'center', inline: 'nearest'})")
    panel.screenshot(path=str(ARTIFACTS / name))


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    token = seed_verified_account({
            "email": f"strategy-e2e-{secrets.token_hex(6)}@example.com",
            "password": secrets.token_urlsafe(24),
        })["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    try:
        seed_test_membership(owner, "strategy-e2e-")
        sessions = {
            row["source_session_key"]: row["id"]
            for row in api("GET", "/api/sessions", token)
        }
        bahrain, imola = (sessions[f"openf1:session:{key}"] for key in (10014, 9987))
        melbourne = sessions.get("openf1:session:11234")
        if melbourne is None:
            catalog = api("GET", "/api/sessions/catalog?season=2026", token)
            item = next(
                row
                for row in catalog
                if row["source_session_key"] == "openf1:session:11234"
            )
            melbourne = api(
                "POST",
                "/api/sessions/import",
                token,
                {
                    "season_year": item["season_year"],
                    "round_number": item["round_number"],
                    "session_name": "Race",
                    "source_session_key": item["source_session_key"],
                    "import_profile": "core",
                },
            )["id"]
        lane_report_query = """import json, sys
from sqlalchemy import select
from modules.storage.infrastructure.db import SessionLocal
from modules.session_domain.infrastructure.db_models import SessionRaceControlMessageRecord as R
with SessionLocal() as db:
    rows = db.execute(select(R.message, R.session_time_ms).where(R.session_id == sys.argv[1], R.message.in_(('PIT LANE ENTRY CLOSED', 'PIT LANE ENTRY OPEN'))))
    print(json.dumps(dict(rows.all())))
"""
        lane = json.loads(
            subprocess.check_output(
                [
                    str(ROOT / "backend/.venv/Scripts/python.exe"),
                    "-c",
                    lane_report_query,
                    melbourne,
                ],
                cwd=ROOT / "backend",
            )
        )
        timings = []

        def strategy(sid, cutoff):
            began = monotonic()
            value = api(
                "POST",
                f"/api/strategy/sessions/{sid}/replay",
                token,
                {"as_of_ms": cutoff},
            )
            timings.append(round(1000 * (monotonic() - began)))
            return value

        normal_cutoff = 9_500_000
        caution_cutoff = 9_735_000
        vsc_cutoff = 9_765_000
        normal = strategy(bahrain, normal_cutoff)
        assert normal["version"] == "replay_strategy_v2"
        drivers = [row for row in normal["drivers"] if row["call"]]
        assert len(drivers) == 20, [
            (row["entry_id"], row["status"])
            for row in normal["drivers"]
            if not row["call"]
        ]
        assert normal["total_laps"] == 57 and normal["pit"]["sample_count"] >= 3
        assert any(
            profile["practice_runs"] for profile in normal["compound_profiles"].values()
        )
        assert strategy(bahrain, 7_200_000)["leader_completed_laps"] == 0
        caution = strategy(imola, caution_cutoff)
        forecast = caution["incident"]["forecast"]
        assert (
            forecast and forecast["episodes"] >= 12 and forecast["races"] >= 3
        ), caution["incident"]
        assert 0 < forecast["outcomes_pct"]["sc"] < 100
        assert abs(sum(forecast["outcomes_pct"].values()) - 100) < 0.001
        candidates = [
            (driver["entry_id"], candidate)
            for driver in caution["drivers"]
            if (call := driver["call"])
            for candidate in (call["best"], call["alternative"])
            if candidate
            and candidate.get("pit_phase", {}).get("basis") == "historical_phase"
            and candidate["neutralisation_saving_s"] > 0
        ]
        assert (
            candidates
        ), "No supported Imola pit option used the historical warning probabilities"
        vsc = strategy(imola, vsc_cutoff)
        assert vsc["incident"]["phase"] == "6"
        assert vsc["pit"]["discount_s"]["vsc"] > 0
        assert strategy(imola, 9_725_000)["incident"]["forecast"] is None
        closed_cutoff = lane["PIT LANE ENTRY CLOSED"] + 5500
        reopened_cutoff = lane["PIT LANE ENTRY OPEN"] + 5500
        closed = strategy(melbourne, closed_cutoff)
        assert (
            closed["incident"]["phase"] == "6"
            and closed["incident"]["pit_entry_closed"]
        )
        assert all(
            row["call"] is None or row["call"]["action"] != "box"
            for row in closed["drivers"]
        )
        assert not strategy(melbourne, reopened_cutoff)["incident"]["pit_entry_closed"]
        ordinary = api("GET", f"/api/sessions/{bahrain}/entries", token)
        matchups = [driver for driver in drivers if driver["matchups"]]
        assert len(matchups) == 20
        focus = next(
            driver
            for driver in matchups
            if {"holds", "boxes"}
            <= {row["assumption"] for row in driver["matchups"][0]["scenarios"]}
            and driver["rivals"][0]["comparison"]
            and all(
                sector["delta_s"] is not None
                for sector in driver["rivals"][0]["comparison"]["sectors"]
            )
        )
        second = next(row for row in drivers if row["entry_id"] != focus["entry_id"])
        post_pit_advantages = [
            abs(choice["post_pit_pace_advantage_s"])
            for item in focus["matchups"]
            for scenario in item["scenarios"]
            for choice in scenario["choices"]
            if choice["post_pit_pace_advantage_s"] is not None
        ]
        assert post_pit_advantages and max(post_pit_advantages) < 5, post_pit_advantages
        assert {row["id"] for row in ordinary} == {row["entry_id"] for row in drivers}
        for sid, code, supplied_token in (
            (sessions["openf1:session:10010"], 422, token),
            (imola, 401, None),
        ):
            try:
                api(
                    "POST",
                    f"/api/strategy/sessions/{sid}/replay",
                    supplied_token,
                    {"as_of_ms": caution_cutoff},
                )
            except HTTPError as error:
                assert error.code == code, error.code
            else:
                raise AssertionError(
                    "Strategy rejected neither an unsupported session nor an anonymous request"
                )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000}, color_scheme="dark"
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/login")
            page.evaluate("token => localStorage.setItem('auth_token', token)", token)

            def open_layout(sid, selected="", mode="simulation"):
                page.goto(
                    f"{BASE}/sessions/{sid}?"
                    + urlencode(
                        {
                            "mode": mode,
                            "layout": "builtin:race-strategy",
                            "drivers": selected,
                        }
                    )
                )

            def seek(stamp):
                slider = page.get_by_role("slider", name="Replay time")
                page.wait_for_function(
                    "stamp => document.querySelector('.sessions-replay-timeline input')?.max > stamp",
                    arg=stamp,
                )
                slider.evaluate(
                    """(input, stamp) => {
                    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, String(stamp));
                    input.dispatchEvent(new Event('input', {bubbles:true}));
                    input.dispatchEvent(new Event('change', {bubbles:true}));
                }""",
                    stamp,
                )

            open_layout(bahrain, f"{focus['entry_id']},{second['entry_id']}")
            call = page.locator('[data-widget="strategy-call"]')
            tyre = page.locator('[data-widget="tyre-outlook"]')
            expect(
                call.get_by_text("Waiting for a supported call", exact=True)
            ).to_be_visible(timeout=30000)
            height = call.bounding_box()["height"]
            seek(normal_cutoff)
            expect(call.locator(".strategy-call-card")).to_have_attribute(
                "data-action", focus["call"]["action"], timeout=30000
            )
            rival = page.locator('[data-widget="rival-comparison"]')
            scenario = page.locator('[data-widget="rival-pit-scenarios"]')
            expect(rival.get_by_label("Recent sector differences")).to_be_visible()
            expect(scenario.get_by_label("Conditional pit options")).to_be_visible()
            expect(
                scenario.get_by_text("Stays out this lap", exact=True)
            ).to_have_count(1)
            scenario.get_by_label("Rival action").select_option("boxes")
            expect(scenario.get_by_label("Rival action")).to_have_value("boxes")
            expect(scenario.get_by_text("branch fits", exact=False)).to_be_visible()
            capture(rival, "rival-sector-comparison.png")
            capture(scenario, "rival-pit-scenarios.png")
            selector = call.get_by_role("combobox", name="Strategy call driver")
            selector.click()
            options = page.get_by_role("listbox", name="Strategy call driver")
            expect(options.get_by_role("option")).to_have_count(20)
            car = next(
                row["car_number"] for row in ordinary if row["id"] == second["entry_id"]
            )
            options.get_by_role("option", name=re.compile(rf"^#{car} ")).click()
            expect(
                tyre.get_by_role("combobox", name="Tyre outlook driver")
            ).to_have_attribute(
                "title",
                re.compile(rf"^#{car} "),
            )
            assert call.bounding_box()["height"] == height
            expect(
                tyre.get_by_text("Practice start to end", exact=False).first
            ).to_be_visible()
            capture(call, "strategy-call.png")
            capture(tyre, "tyre-outlook.png")
            start = page.get_by_role("button", name="Start", exact=True)
            expect(start).to_be_enabled(timeout=30000)
            with page.expect_request(
                lambda request: request.url.endswith("/replay")
                and request.method == "POST"
                and request.post_data_json["as_of_ms"] >= normal_cutoff + 5000,
                timeout=15000,
            ):
                start.click()
            page.get_by_role("button", name="Pause", exact=True).click()
            assert call.bounding_box()["height"] == height

            open_layout(imola, candidates[0][0])
            risk = page.locator('[data-widget="intervention-risk"]')
            seek(caution_cutoff)
            expect(risk.locator(".strategy-risk-chart")).to_be_visible(timeout=30000)
            expect(risk.locator(".strategy-warning-feed")).to_contain_text(
                "Yellow flag"
            )
            expect(risk.locator(".strategy-warning-feed b")).to_contain_text("% SC")
            expect(call.locator(".strategy-pit-phase")).to_contain_text("% VSC")
            capture(risk, "incident-forecast.png")
            risk.get_by_text("Yellow flag", exact=True).first.click()
            expect(
                risk.get_by_text("YELLOW IN TRACK SECTOR", exact=False)
            ).to_be_visible()
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
            capture(risk, "incident-forecast-mobile.png")
            seek(vsc_cutoff)
            expect(
                risk.get_by_text("Virtual safety car in effect", exact=True)
            ).to_be_visible(timeout=30000)
            expect(risk.locator(".strategy-risk-chart")).to_have_count(0)
            seek(9_725_000)
            expect(
                risk.get_by_text("Virtual safety car in effect", exact=True)
            ).to_have_count(0)
            expect(risk.locator(".strategy-risk-chart")).to_have_count(0)
            open_layout(melbourne)
            seek(closed_cutoff)
            expect(risk.get_by_text("Pit entry closed", exact=True)).to_be_visible(
                timeout=30000
            )
            capture(risk, "melbourne-pit-entry-closed.png")
            seek(reopened_cutoff)
            expect(risk.get_by_text("Pit entry closed", exact=True)).to_have_count(0)
            open_layout(imola, mode="lookback")
            expect(page.locator(".layout-availability-message")).to_be_visible()
            assert not errors, errors
            browser.close()

        result = {
            "bahrain_plans": len(drivers),
            "bahrain_green_pit_samples": normal["pit"]["sample_count"],
            "bahrain_green_pit_basis": normal["pit"]["green_basis"],
            "bahrain_drivers_with_rival_scenarios": len(matchups),
            "bahrain_focus_max_post_pit_advantage_s_per_lap": round(
                max(post_pit_advantages), 3
            ),
            "imola_warning_weighted_pit_options": len(candidates),
            "imola_vsc_pit_discount_s": vsc["pit"]["discount_s"]["vsc"],
            "imola_vsc_pit_basis": vsc["pit"]["discount_basis"]["vsc"],
            "melbourne_pit_lane_closure_checked": True,
            "imola_incident_forecast": forecast,
            "api_latency_ms": timings,
            "browser": "Rival action, sector deltas, shared driver selection, replay cutoff, VSC replaces forecast, rewind, desktop/mobile, lookback blocked",
        }
        (ARTIFACTS / "results.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, indent=2))
    finally:
        cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    row = db.get(UserRecord, sys.argv[1])
    if row and row.email.startswith('strategy-e2e-'):
        db.delete(row)
        db.commit()
"""
        subprocess.run(
            [str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", cleanup, owner],
            cwd=ROOT / "backend",
            check=True,
        )


if __name__ == "__main__":
    main()
