"""Verify that the real qualifying workspace draws audited apex samples and mapped roads."""
from local_test_accounts import seed_verified_account

import json
import re
import secrets
import subprocess
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright

from check_session_review_browser import BASE, ROOT, api

ARTIFACTS = ROOT / "docs/testing/replay-map"
ROUNDS = {"Sakhir": 4, "Suzuka": 3, "Silverstone": 12, "Imola": 7}


def main():
    audit = json.loads((ARTIFACTS / "qualifying-track-positions.json").read_text(encoding="utf-8"))
    email = f"qualifying-map-browser-{secrets.token_hex(6)}@example.com"
    credentials = {"email": email, "password": secrets.token_urlsafe(24)}
    token = seed_verified_account(credentials)["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    checks = []
    errors = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="dark")
            page.add_init_script(f"localStorage.setItem('auth_token', {json.dumps(token)});")
            page.on("pageerror", lambda error: errors.append(str(error)))
            for result in audit["circuits"]:
                name = result["circuit"]
                session = api("POST", "/api/sessions/import", token, {
                    "season_year": 2025, "round_number": ROUNDS[name], "session_name": "Qualifying",
                    "source_session_key": f"openf1:session:{result['session_key']}", "import_profile": "core",
                })
                sid = session["id"]
                entries = api("GET", f"/api/sessions/{sid}/entries", token)
                entry = next(item for item in entries if item["car_number"] == str(result["driver"]))
                params = urlencode({
                    "mode": "lookback", "layout": "builtin:session-trends",
                    "drivers": entry["id"], "lap": result["lap"],
                })
                page.goto(f"{BASE}/sessions/{sid}?{params}")
                panel = page.locator('[data-widget="session-track-map"]')
                line = panel.locator(".track-map-viewer__racing-line")
                expect(line).to_have_count(1, timeout=180000)
                x, y = result["corner"]["openf1_xy_in_apex_out"][1]
                expect(line).to_have_attribute("d", re.compile(rf"(?<!\S){re.escape(f'{x:.2f} {y:.2f}')}(?!\S)"))
                for _ in range(3):
                    panel.get_by_role("button", name="Zoom in", exact=True).click()
                road = panel.locator('[data-road-source="mapped"]')
                expect(road).to_have_count(1)
                if name == "Imola":
                    expect(panel.get_by_text("Mapped centreline with estimated width.", exact=False)).to_be_visible()
                else:
                    expect(panel.get_by_text("Mapped road edges.", exact=False)).to_be_visible()
                if name == "Sakhir":
                    panel.scroll_into_view_if_needed()
                    panel.screenshot(path=str(ARTIFACTS / "qualifying-bahrain-map.png"))
                    width_pattern = "**/circuit-roads/Sakhir.csv"
                    def omit_width(route):
                        route.abort()
                    page.route(width_pattern, omit_width)
                    try:
                        with page.expect_response(lambda response: response.url.endswith("/circuit-roads/centrelines/bh-2002.csv")):
                            page.reload()
                        expect(panel.get_by_text("Mapped centreline with estimated width.", exact=False)).to_be_visible()
                    finally:
                        page.unroute(width_pattern, omit_width)
                    print("Sakhir loaded its centreline when the width profile was unavailable.", flush=True)
                checks.append({"circuit": name, "lap": result["lap"], "audited_apex_drawn": True, "mapped_road_drawn": True})
                print(checks[-1], flush=True)
            assert not errors, errors
            browser.close()
    finally:
        cleanup = """import sys
from modules.identity_auth.infrastructure.db_models import UserRecord
from modules.storage.infrastructure.db import SessionLocal
with SessionLocal() as db:
    row = db.get(UserRecord, sys.argv[1])
    if row and row.email.startswith('qualifying-map-browser-'):
        db.delete(row)
        db.commit()
"""
        subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", cleanup, owner], cwd=ROOT / "backend", check=True)
    (ARTIFACTS / "qualifying-map-browser.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
