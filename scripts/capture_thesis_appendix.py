"""Capture the current layout editor and real replay panels without account chrome."""
from local_test_accounts import seed_verified_account

import json
import secrets
import subprocess
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright

from check_session_review_browser import BASE, ROOT, api
from check_timing_tower import seek

OUTPUT = ROOT / "docs/testing/thesis-appendix"


def capture_top(page, element, filename, max_height):
    element.scroll_into_view_if_needed()
    bounds = element.bounding_box()
    scroll = page.evaluate("({x: scrollX, y: scrollY})")
    assert bounds is not None
    page.screenshot(
        path=OUTPUT / filename,
        full_page=True,
        clip={
            "x": bounds["x"] + scroll["x"],
            "y": bounds["y"] + scroll["y"],
            "width": bounds["width"],
            "height": min(bounds["height"], max_height),
        },
    )


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    token = seed_verified_account({
            "email": f"thesis-capture-{secrets.token_hex(6)}@example.com",
            "password": secrets.token_urlsafe(24),
        })["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    try:
        imola = next(
            row["id"]
            for row in api("GET", "/api/sessions", token)
            if row["source_session_key"] == "openf1:session:9987"
        )
        entries = api("GET", f"/api/sessions/{imola}/entries", token)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1550, "height": 1100},
                color_scheme="dark",
                reduced_motion="reduce",
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script(
                f"localStorage.setItem('auth_token', {json.dumps(token)});"
            )
            page.goto(BASE + "/dashboard-builder?audience=live-race&sessionKind=race")
            page.get_by_role("button", name="+ New layout", exact=True).click()
            page.get_by_label("Layout name", exact=True).fill("Race control review")
            search = page.get_by_label("Search widgets", exact=True)
            search.fill("replay track map")
            page.get_by_role("button", name="Add Replay Track Map", exact=True).click()
            search.fill("notifications")
            page.get_by_role(
                "button", name="Add Race notifications", exact=True
            ).click()
            editor = page.get_by_role("region", name="Layout editor", exact=True)
            search.fill("")
            page.add_style_tag(
                content=".app-header { visibility:hidden } .editor-toolbar { position:static }"
            )
            capture_top(page, editor, "layout-editor.png", 960)
            page.get_by_role(
                "button", name="Configure Race notifications", exact=True
            ).click()
            properties = page.locator(".editor-properties")
            expect(properties.get_by_label("Messages shown")).to_be_visible()
            capture_top(page, properties, "notification-settings.png", 670)

            drivers = ",".join(
                row["id"] for row in entries if row["car_number"] in {"1", "4", "81"}
            )
            params = urlencode({"mode": "simulation", "drivers": drivers})
            page.goto(f"{BASE}/sessions/{imola}?{params}")
            viewer = page.get_by_role("button", name="Race viewer", exact=True)
            viewer.click()
            expect(viewer).to_have_attribute("aria-pressed", "true")
            seek(page, 9_765_000)
            feed = page.locator('[data-insight-panel="race-notifications"]')
            messages = feed.get_by_role(
                "list", name="Recent race messages"
            ).get_by_role("listitem")
            expect(messages.first).to_be_visible(timeout=30_000)
            page.locator('[data-widget="race-notifications"]').screenshot(
                path=OUTPUT / "race-updates.png"
            )
            assert not errors, errors
            browser.close()
    finally:
        cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    user = db.get(UserRecord, sys.argv[1])
    if user and user.email.startswith('thesis-capture-'):
        db.delete(user)
        db.commit()
"""
        subprocess.run(
            [str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", cleanup, owner],
            cwd=ROOT / "backend",
            check=True,
        )


if __name__ == "__main__":
    main()
