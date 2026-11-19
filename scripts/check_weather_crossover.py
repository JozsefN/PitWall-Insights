"""Exercise the crossover panel and timed rain scenarios with stored OpenF1 races."""

from datetime import datetime, timedelta
import json
import secrets
import subprocess
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright
from check_session_review_browser import API, BASE, ROOT, api

ARTIFACTS = ROOT / "docs/testing/replay-strategy"
CASES = {
    "silverstone": (9558, 2024, "2024-07-07T14:00:00+00:00"),
    "melbourne": (9693, 2025, "2025-03-16T04:00:00+00:00"),
    "canada": (9531, 2024, "2024-06-09T18:00:00+00:00"),
    "bahrain": (10014, 2025, "2025-04-13T15:00:00+00:00"),
}


def cutoff(case, date):
    start = datetime.fromisoformat(CASES[case][2]) - timedelta(hours=2)
    return round((datetime.fromisoformat(date) - start).total_seconds() * 1000)


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    email = f"crossover-e2e-{secrets.token_hex(6)}@example.com"
    token = api(
        "POST",
        "/api/auth/signup",
        payload={
            "email": email,
            "password": secrets.token_urlsafe(24),
        },
    )["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    try:
        sessions = {
            row["source_session_key"]: row["id"]
            for row in api("GET", "/api/sessions", token)
        }
        ids = {}
        for label, (source, year, _) in CASES.items():
            key = f"openf1:session:{source}"
            if key not in sessions:
                catalog = api("GET", f"/api/sessions/catalog?season={year}", token)
                item = next(row for row in catalog if row["source_session_key"] == key)
                sessions[key] = api(
                    "POST",
                    "/api/sessions/import",
                    token,
                    {
                        "season_year": year,
                        "round_number": item["round_number"],
                        "session_name": "Race",
                        "source_session_key": key,
                        "import_profile": "core",
                    },
                )["id"]
            ids[label] = sessions[key]

        def driver_id(case, car):
            rows = api("GET", f"/api/sessions/{ids[case]}/entries", token)
            return next(row["id"] for row in rows if str(row["car_number"]) == car)

        def strategy(case, stamp, rain=None):
            return api(
                "POST",
                f"/api/strategy/sessions/{ids[case]}/replay",
                token,
                {"as_of_ms": stamp, "rain_scenario": rain},
            )

        silverstone = cutoff("silverstone", "2024-07-07T15:05:50+00:00")
        melbourne = cutoff("melbourne", "2025-03-16T05:39:45+00:00")
        canada = cutoff("canada", "2024-06-09T18:06:15+00:00")
        bahrain = cutoff("bahrain", "2025-04-13T15:28:00+00:00")
        dry = strategy("silverstone", silverstone)["crossover"]
        wet = strategy("melbourne", melbourne)["crossover"]
        wets = strategy("canada", canada)["crossover"]
        norris, max_id = driver_id("silverstone", "4"), driver_id("melbourne", "1")
        assert dry["field"]["SLICK"] > 1 and dry["field"]["INTERMEDIATE"] > 1, dry
        early = next(
            row
            for row in dry["decisions"][norris]["options"]
            if row["target"] == "SLICK"
        )
        assert 2 in [row["sector"] for row in early["sectors"]], early
        max_choice = wet["decisions"][max_id]
        assert max_choice["target"] == "INTERMEDIATE", max_choice
        assert wets["field"]["WET"] == 2, wets["field"]
        manual = {
            "issued_at_ms": bahrain,
            "starts_at_ms": bahrain + 120_000,
            "ends_at_ms": bahrain + 480_000,
            "probability_pct": 85,
            "intensity": "heavy",
        }
        rain = strategy("bahrain", bahrain, manual)["crossover"]
        assert (
            rain["forecast"]
            and rain["field"]["WET"] == 0
            and rain["field"]["INTERMEDIATE"] == 0
        )
        assert any(row["options"] for row in rain["decisions"].values())
        assert (
            strategy("bahrain", bahrain - 5000, manual)["crossover"]["forecast"] is None
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1400, "height": 1000}, color_scheme="dark"
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/login")
            page.evaluate("token => localStorage.setItem('auth_token', token)", token)

            def open_layout(case, driver=""):
                page.goto(
                    f"{BASE}/sessions/{ids[case]}?"
                    + urlencode(
                        {
                            "mode": "simulation",
                            "layout": "builtin:race-strategy",
                            "drivers": driver,
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

            pane = page.locator('[data-widget="tyre-crossover"]')
            open_layout("silverstone", norris)
            seek(silverstone)
            expect(pane.get_by_label("Matched sector differences").first).to_be_visible(
                timeout=30000
            )
            pane.screenshot(path=str(ARTIFACTS / "silverstone-crossover.png"))

            open_layout("melbourne", max_id)
            seek(melbourne)
            expect(pane.get_by_label("Crossover tyre options")).to_be_visible(
                timeout=30000
            )
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
            pane.screenshot(path=str(ARTIFACTS / "melbourne-crossover-mobile.png"))
            page.set_viewport_size({"width": 1400, "height": 1000})

            open_layout("bahrain", driver_id("bahrain", "4"))
            seek(bahrain)
            expect(
                pane.get_by_text("Crossover timing appears", exact=False)
            ).to_be_visible(timeout=30000)
            pane.get_by_text("Test an incoming rain scenario", exact=True).click()
            pane.get_by_label("Intensity").select_option("heavy")
            with page.expect_request(
                lambda request: request.url.startswith(API)
                and request.url.endswith("/replay")
                and request.post_data_json.get("rain_scenario")
            ):
                pane.get_by_role("button", name="Apply scenario").click()
            expect(pane.get_by_text("chance of heavy rain", exact=False)).to_be_visible(
                timeout=30000
            )
            expect(pane.get_by_label("Crossover tyre options")).to_be_visible()
            pane.screenshot(path=str(ARTIFACTS / "bahrain-rain-scenario.png"))
            seek(bahrain - 5000)
            expect(pane.get_by_text("chance of heavy rain", exact=False)).to_have_count(
                0
            )
            assert not errors, errors
            browser.close()

        result = {
            "silverstone_early_sector": early,
            "melbourne_switch": max_choice,
            "canada_full_wet_cars": wets["field"]["WET"],
            "bahrain_rain_scenario_before_first_switch": True,
            "browser": [
                "Early sectors",
                "Mobile",
                "Rain scenario",
                "Rewind hides unissued scenario",
            ],
        }
        (ARTIFACTS / "weather-crossover-workflow.json").write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, indent=2))
    finally:
        cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    row = db.get(UserRecord, sys.argv[1])
    if row and row.email.startswith('crossover-e2e-'):
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
