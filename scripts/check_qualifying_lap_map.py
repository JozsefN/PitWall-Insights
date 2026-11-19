"""Exercise the qualifying timing map and field preparation against local OpenF1 history."""
from filter_controls import select_control

import json
import os
import re
import secrets
import subprocess
from time import monotonic

from playwright.sync_api import expect, sync_playwright

from check_session_review_browser import BASE, ROOT, api

ARTIFACTS = ROOT / "docs/testing/qualifying-lap-map"


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    email = f"qualifying-map-e2e-{secrets.token_hex(6)}@example.com"
    token = api("POST", "/api/auth/signup", payload={"email": email, "password": secrets.token_urlsafe(24)})["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    try:
        key = os.environ.get("PITWALL_QUALIFYING_MAP_SESSION", "10010")
        sid = next(row["id"] for row in api("GET", "/api/sessions", token) if row["source_session_key"] == f"openf1:session:{key}")
        race_id = next(row["id"] for row in api("GET", "/api/sessions", token) if row["source_session_key"] == "openf1:session:9987")
        path = f"/api/feature-metrics/sessions/{sid}/qualifying-lap"
        official = api("GET", path, token)
        assert len(official["sectors"]) == 3
        timed_drivers = len({lap["entry_id"] for lap in official["laps"]})
        assert all(len(split["ranking"]) == timed_drivers for split in official["sectors"])
        from urllib.error import HTTPError
        try:
            api("GET", f"/api/feature-metrics/sessions/{race_id}/qualifying-lap", token)
        except HTTPError as error:
            assert error.status == 422, error
        else:
            raise AssertionError("Race sessions must reject the qualifying API")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="dark")
            errors = []
            page.on("pageerror", lambda event: errors.append(str(event)))
            page.goto(BASE + "/login")
            page.evaluate("token => localStorage.setItem('auth_token', token)", token)
            page.goto(BASE + f"/sessions/{sid}?mode=lookback&layout=builtin:qualifying-review")
            panel = page.locator('[data-widget="qualifying-lap-map"]')
            expect(panel.get_by_role("heading", name="Sector 1")).to_be_visible(timeout=30000)
            expect(panel.locator("tbody tr")).to_have_count(timed_drivers)
            panel.get_by_role("button", name="Sector 2", exact=True).click()
            expect(panel.get_by_role("heading", name="Sector 2")).to_be_visible()
            started = monotonic()
            panel.get_by_role("button", name="Minisectors", exact=True).click()
            print(f"Preparing qualifying field positions for session {key}", flush=True)
            note = panel.locator(".qualifying-lap__note")
            expect(note).to_contain_text("comparable laps", timeout=30000)
            expect(note).not_to_contain_text("Loading field positions", timeout=300000)
            expect(note).not_to_contain_text("could not be loaded")
            expect(panel.get_by_role("button", name="Minisector 20", exact=True)).to_be_visible(timeout=60000)

            mini = api("GET", path + "?minisectors=true", token)
            assert mini["minisector_driver_count"] >= timed_drivers - 1, mini["minisector_driver_count"]
            assert mini["focus_minisectors_available"], mini["focus"]
            assert len(mini["minisectors"]) == 20
            expect(panel.locator("tbody tr")).to_have_count(mini["minisector_driver_count"])
            expect(panel.locator("svg [data-split-colour]")).to_have_count(20)
            hit = panel.locator(".qualifying-lap__hit").nth(6)
            hit.scroll_into_view_if_needed()
            point = hit.evaluate("""path => {
                const point = path.getPointAtLength(path.getTotalLength() / 2).matrixTransform(path.getScreenCTM());
                return { x: point.x, y: point.y };
            }""")
            page.mouse.click(point["x"], point["y"])
            expect(panel.get_by_role("heading", name="Minisector 7", exact=True)).to_be_visible()
            expect(panel.get_by_role("button", name="Minisector 7", exact=True)).to_have_attribute("aria-pressed", "true")

            other = next(row for row in mini["laps"] if row["entry_id"] != mini["focus"]["entry_id"])
            select_control(panel.get_by_label("Qualifying lap driver"), other["entry_id"])
            expect(panel.get_by_label("Qualifying timed lap")).to_have_value(str(other["lap_number"]))
            expect(panel.locator(".qualifying-lap__timing p").first).to_contain_text(
                f"Lap {other['lap_number']}", timeout=30000,
            )
            panel.screenshot(path=str(ARTIFACTS / f"{key}-minisectors.png"))
            panel.get_by_role("button", name="Sectors", exact=True).click()
            expect(panel.get_by_role("button", name="Sector 3", exact=True)).to_be_visible()
            expect(panel.locator("tbody tr")).to_have_count(timed_drivers)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
            panel.screenshot(path=str(ARTIFACTS / f"{key}-mobile-sectors.png"))
            cards = page.locator('[data-widget="lookback-driver-cards"]')
            cards.get_by_role("button", name="Q1", exact=True).click(timeout=30000)
            expect(cards.locator("[data-phase='2']")).to_have_count(0)
            lap_button = cards.get_by_role("button", name="Inspect lap", exact=False).first
            expect(lap_button).to_be_visible(timeout=30000)
            lap_number = lap_button.inner_text().split()[-1]
            entry_id = lap_button.locator("xpath=ancestor::article[1]").get_attribute("data-entry-id")
            cards.screenshot(path=str(ARTIFACTS / f"{key}-driver-cards-mobile.png"))
            lap_button.click()
            expect(panel.get_by_label("Qualifying lap driver")).to_have_attribute("data-value", entry_id)
            expect(panel.get_by_label("Qualifying timed lap")).to_have_value(lap_number)
            expect(panel.locator(".qualifying-lap__timing p").first).to_contain_text(
                f"Lap {lap_number}", timeout=30000,
            )
            expect(panel.get_by_label("Qualifying lap driver")).to_be_focused()
            assert not errors, errors
            browser.close()

        report = {"session_key": key, "field": official["field_driver_count"],
                  "official_sector_ranked_drivers": len(official["sectors"][0]["ranking"]),
                  "minisector_ranked_drivers": mini["minisector_driver_count"],
                  "comparable_laps": mini["minisector_lap_count"], "minisectors": 20,
                  "workflow_seconds": round(monotonic() - started, 2)}
        (ARTIFACTS / f"{key}-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    row = db.get(UserRecord, sys.argv[1])
    if row and row.email.startswith('qualifying-map-e2e-'):
        db.delete(row)
        db.commit()
"""
        subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", cleanup, owner], cwd=ROOT / "backend", check=True)


if __name__ == "__main__":
    main()
