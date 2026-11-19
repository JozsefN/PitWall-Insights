"""Check all builder scopes, saved layouts and replay timing with real sessions."""

import json
import secrets
import subprocess
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright
from check_session_review_browser import BASE, ROOT, api

ARTIFACTS = ROOT / "docs/testing/replay-strategy"
LAYOUTS = {
    "Grand Prix": (10014, "Race review", "Race viewer"),
    "Sprint": (11275, "Sprint review", "Sprint replay"),
    "Qualifying": (10010, "Qualifying review", "Qualifying replay"),
    "Practice": (10008, "Practice analysis", "Practice replay"),
    "Sprint Qualifying": (11271, "Qualifying review", "Qualifying replay"),
}


def seek(slider, stamp):
    slider.evaluate(
        """(input, stamp) => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, String(stamp));
        input.dispatchEvent(new Event('input', {bubbles:true}));
        input.dispatchEvent(new Event('change', {bubbles:true}));
    }""",
        stamp,
    )


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    token = api(
        "POST",
        "/api/auth/signup",
        payload={
            "email": f"layout-matrix-{secrets.token_hex(6)}@example.com",
            "password": secrets.token_urlsafe(24),
        },
    )["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    try:
        sessions = {
            row["source_session_key"]: row["id"]
            for row in api("GET", "/api/sessions", token)
        }
        sprint_qualifying = "openf1:session:11271"
        if sprint_qualifying not in sessions:
            catalog = api("GET", "/api/sessions/catalog?season=2026", token)
            event = next(
                row for row in catalog if row["source_session_key"] == sprint_qualifying
            )
            session = api(
                "POST",
                "/api/sessions/import",
                token,
                {
                    "season_year": event["season_year"],
                    "round_number": event["round_number"],
                    "session_name": event["session_name"],
                    "source_session_key": sprint_qualifying,
                    "import_profile": "core",
                },
            )
            sessions[sprint_qualifying] = session["id"]
        report = {}
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1440, "height": 1024}, color_scheme="light"
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/login")
            page.evaluate("token => localStorage.setItem('auth_token', token)", token)
            page.goto(BASE + "/dashboard-builder")
            scope = page.get_by_role("group", name="Session type")
            audience = page.get_by_role("group", name="Dashboard audience")

            for kind, (_, lookback, replay) in LAYOUTS.items():
                if kind == "Sprint Qualifying":
                    continue
                scope.get_by_role("button", name=kind, exact=True).click()
                for mode, expected in (("Lookback", lookback), ("Replay", replay)):
                    audience.get_by_role("button", name=mode, exact=True).click()
                    expect(
                        scope.get_by_role("button", name=kind, exact=True)
                    ).to_have_attribute("aria-pressed", "true")
                    expect(
                        page.locator(".builder-card-select").first
                    ).to_have_attribute("aria-label", f"Preview {expected}")
                    if kind != "Grand Prix":
                        expect(
                            page.get_by_role(
                                "button", name="Preview Race strategy", exact=True
                            )
                        ).to_have_count(0)
                        expect(
                            page.get_by_text("Unavailable in sessions:", exact=False)
                        ).to_have_count(0)
            page.screenshot(path=str(ARTIFACTS / "builder-practice-desktop.png"))
            page.get_by_role(
                "button", name="Preview Practice replay", exact=True
            ).click()
            dialog = page.get_by_role("dialog", name="Practice replay")
            expect(dialog).to_be_visible()
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
            dialog.screenshot(
                path=str(ARTIFACTS / "builder-practice-preview-mobile.png")
            )
            page.keyboard.press("Escape")
            expect(dialog).to_have_count(0)
            page.set_viewport_size({"width": 1440, "height": 1024})

            page.get_by_role("button", name="New layout", exact=False).click()
            expect(page.get_by_label("Session type")).to_have_value("practice")
            page.get_by_label("Layout name").fill("Practice timing only")
            search = page.get_by_role("searchbox", name="Search widgets")
            search.fill("Strategy call")
            expect(
                page.get_by_role("button", name="Add Strategy call", exact=True)
            ).to_be_disabled()
            expect(
                page.get_by_role("complementary", name="Widget library").get_by_text(
                    "Grand Prix only", exact=True
                )
            ).to_be_visible()
            search.fill("Replay timing board")
            page.get_by_role(
                "button", name="Add Replay timing board", exact=True
            ).click()
            page.get_by_role("button", name="Save layout", exact=True).click()
            saved = page.get_by_role(
                "button", name="Preview Practice timing only", exact=True
            )
            expect(saved).to_be_visible()
            expect(
                page.get_by_role("status").get_by_text("Layout saved to your profile.")
            ).to_be_visible()
            page.get_by_role(
                "button", name="Favorite Practice timing only", exact=True
            ).click()
            expect(page.locator(".builder-card-select").first).to_have_attribute(
                "aria-label", "Preview Practice timing only"
            )

            for kind, (source, lookback, replay) in LAYOUTS.items():
                session = sessions[f"openf1:session:{source}"]
                for mode, expected in (("lookback", lookback), ("simulation", replay)):
                    page.goto(f"{BASE}/sessions/{session}?" + urlencode({"mode": mode}))
                    strip = page.get_by_label("Compatible layouts")
                    first = (
                        "Practice timing only"
                        if kind == "Practice" and mode == "simulation"
                        else expected
                    )
                    expect(
                        strip.locator(".sessions-layout-card").first
                    ).to_have_attribute("aria-label", first)
                    if kind != "Grand Prix":
                        expect(
                            strip.get_by_role(
                                "button", name="Race strategy", exact=True
                            )
                        ).to_have_count(0)
                    strip.get_by_role("button", name=expected, exact=True).click()
                    expect(
                        page.get_by_role("link", name="Jump to dashboard", exact=False)
                    ).to_be_visible()
                    if kind == "Sprint Qualifying" and mode == "lookback":
                        phase = page.get_by_role("group", name="Qualifying phase")
                        phase.get_by_role("button", name="SQ1", exact=True).click(
                            timeout=30000
                        )
                        expect(
                            phase.get_by_role("button", name="SQ1", exact=True)
                        ).to_have_attribute("aria-pressed", "true")
                report[kind] = ["Lookback", "Replay"]
                if kind == "Grand Prix":
                    continue
                slider = page.get_by_role("slider", name="Replay time")
                timing = page.locator('[data-widget="replay-timing-board"]')
                if kind == "Practice":
                    strip.get_by_role(
                        "button", name="Practice timing only", exact=True
                    ).click()
                expect(
                    timing.get_by_text("Waiting for a valid completed lap.", exact=True)
                ).to_be_visible(timeout=30000)
                maximum = int(slider.get_attribute("max"))
                minimum = int(slider.get_attribute("min"))
                if kind == "Practice":
                    page.locator(".sessions-driver-actions").get_by_role(
                        "button", name="All", exact=True
                    ).click()
                seek(slider, maximum - 5000)
                expect(timing.get_by_role("table")).to_be_visible(timeout=30000)
                if kind == "Practice":
                    expect(timing.locator("tbody tr")).to_have_count(20, timeout=30000)
                field = timing.locator("tbody tr").count()
                assert field >= 2, (kind, field)
                if kind == "Qualifying":
                    timing.screenshot(
                        path=str(ARTIFACTS / "qualifying-timing-board.png")
                    )
                seek(slider, minimum)
                expect(timing.get_by_role("table")).to_have_count(0)
                report[kind].append(
                    f"replay timing populated and rewound with {field} drivers"
                )
            assert not errors, errors
            browser.close()
        (ARTIFACTS / "layout-matrix.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
    finally:
        cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    row = db.get(UserRecord, sys.argv[1])
    if row and row.email.startswith('layout-matrix-'):
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
