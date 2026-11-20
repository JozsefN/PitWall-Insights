"""Verify the shared timing tower against archived sessions and the real browser UI."""
from local_test_accounts import seed_verified_account

from time import perf_counter
from urllib.parse import urlencode
import json
import secrets
import subprocess

from playwright.sync_api import expect, sync_playwright

from check_session_review_browser import BASE, ROOT, api


def seek(page, stamp):
    slider = page.get_by_role("slider", name="Replay time")
    page.wait_for_function(
        "stamp => Number(document.querySelector('.sessions-replay-timeline input')?.max) >= stamp",
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


def main():
    artifacts = ROOT / "docs/testing/timing-tower"
    artifacts.mkdir(parents=True, exist_ok=True)
    email = f"tower-e2e-{secrets.token_hex(6)}@example.com"
    token = seed_verified_account({"email": email, "password": secrets.token_urlsafe(20)})["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    try:
        sessions = {
            row["source_session_key"]: row for row in api("GET", "/api/sessions", token)
        }
        cases = {
            "race": (2025, 7, "Race", "9987"),
            "qualifying": (2025, 7, "Qualifying", "9983"),
            "practice": (2025, 4, "Practice 2", "10008"),
            "sprint": (2026, 4, "Sprint", "11275"),
        }
        ids, streams, report = {}, {}, {}
        request_counts = []
        for case, (year, round_no, name, source) in cases.items():
            key = f"openf1:session:{source}"
            row = sessions.get(key) or api(
                "POST",
                "/api/sessions/import",
                token,
                {
                    "season_year": year,
                    "round_number": round_no,
                    "session_name": name,
                    "source_session_key": key,
                    "import_profile": "core",
                },
            )
            sid = ids[case] = row["id"]
            start = perf_counter()
            stream = streams[case] = api(
                "GET", f"/api/feature-metrics/sessions/{sid}/timing-tower", token
            )
            report[case] = {
                "entries": row["entry_count"],
                "size_bytes": len(json.dumps(stream, separators=(",", ":"))),
                "request_ms": round((perf_counter() - start) * 1000),
                "interval_samples": sum(map(len, stream["gaps"].values())),
            }

        race = streams["race"]
        assert (
            race["scheduled_laps"] == 63 and report["race"]["interval_samples"] > 5000
        )
        assert any(
            gap is not None and gap < 0
            for rows in race["gaps"].values()
            for _, gap, _ in rows
        )
        green = race["race_crossings"][14][0] + 7000
        safety_car = (
            next(time for time, flag, _ in race["flags"] if flag == "SAFETY CAR") + 3000
        )
        bounds = api("GET", f"/api/sessions/{ids['race']}/replay-timeline", token)
        entries = api("GET", f"/api/sessions/{ids['race']}/entries", token)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1536, "height": 960},
                color_scheme="dark",
                reduced_motion="reduce",
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "request",
                lambda r: (
                    request_counts.append(r.url)
                    if r.url.endswith("/timing-tower")
                    else None
                ),
            )
            page.add_init_script(
                f"localStorage.setItem('auth_token', {json.dumps(token)});"
            )

            def open_session(case, mode="simulation", **params):
                page.goto(
                    f"{BASE}/sessions/{ids[case]}?"
                    + urlencode({"mode": mode, **params})
                )

            def capture(name):
                page.screenshot(path=str(artifacts / name), animations="disabled")

            open_session("race")
            tower = page.get_by_role("complementary", name="Timing tower")
            table = tower.get_by_role("table")
            field = table.locator("tbody tr")
            expect(field).to_have_count(len(entries))
            expect(tower.get_by_text("Lap 1 / 63", exact=True)).to_be_visible()
            initial = field.all_inner_texts()
            seek(page, green)
            expect(tower.get_by_text("Lap 16 / 63", exact=True)).to_be_visible()
            leader_values = field.all_inner_texts()
            assert leader_values != initial
            tower.get_by_role("button", name="Interval").click()
            expect(tower.get_by_role("columnheader", name="Car ahead")).to_be_visible()
            assert field.all_inner_texts() != leader_values
            seek(page, safety_car)
            expect(tower.get_by_text("Safety car", exact=True)).to_be_visible()
            seek(page, bounds["start_time_ms"])
            expect(tower.get_by_text("Lap 1 / 63", exact=True)).to_be_visible()
            expect(tower.get_by_text("Safety car", exact=True)).to_have_count(0)
            assert len(request_counts) == 1, request_counts

            replay_focus = page.get_by_role("button", name="Replay Focus", exact=True)
            replay_focus.click()
            expect(replay_focus).to_have_attribute("aria-pressed", "true")
            expect(field).to_have_count(len(entries))
            expect(tower.get_by_role("button", name="Interval")).to_have_attribute(
                "aria-pressed", "true"
            )
            for index in (0, 1):
                driver = page.locator(".sessions-driver-chip").nth(index)
                driver.click()
                expect(driver).to_have_attribute("aria-pressed", "true")
            seek(page, green)
            expect(page.get_by_label("Top-down track map")).to_be_attached(timeout=30_000)
            page.get_by_role("link", name="Jump to dashboard").click()
            expect(tower).to_be_in_viewport()
            height = page.evaluate(
                "document.querySelector('.app-header').getBoundingClientRect().height"
            )
            page.evaluate("window.scrollBy({top: 260, behavior: 'instant'})")
            top = tower.bounding_box()["y"]
            assert height <= top < height + 30, (height, top, page.evaluate("scrollY"))
            page.evaluate("window.scrollBy({top: -110, behavior: 'instant'})")
            capture("desktop-replay-dark.png")

            page.set_viewport_size({"width": 1366, "height": 768})
            page.get_by_role("link", name="Jump to dashboard").click()
            page.evaluate("window.scrollBy({top: 245, behavior: 'instant'})")
            tower_top = tower.bounding_box()["y"]
            header_bottom = page.locator(".app-header").bounding_box()["height"]
            assert tower_top >= header_bottom, (tower_top, header_bottom)
            table_scroll = tower.get_by_role("region", name="Full-field standings")
            table_scroll.evaluate("node => node.scrollTop = 10000")
            expect(field.last).to_be_in_viewport()
            collapse = tower.get_by_role("button", name="Collapse timing tower")
            stage = page.locator(".sessions-workspace__stage")
            before = stage.bounding_box()["width"]
            collapse.click()
            dock = page.get_by_role("button", name="Open timing tower")
            expect(dock).to_be_focused()
            assert stage.bounding_box()["width"] > before + 210
            dock.click()
            expect(collapse).to_be_focused()

            page.set_viewport_size({"width": 390, "height": 844})
            expect(tower).to_have_count(0)
            expect(dock).to_be_in_viewport()
            dock.click()
            sheet = page.get_by_role("dialog", name="Timing tower")
            expect(sheet).to_be_visible()
            expect(
                sheet.get_by_role("button", name="Close timing tower")
            ).to_be_focused()
            expect(sheet.get_by_role("columnheader", name="Car ahead")).to_be_visible()
            scroller = sheet.get_by_role("region", name="Full-field standings")
            scroller.evaluate("node => node.scrollTop = 10000")
            expect(sheet.locator("tbody tr").last).to_be_in_viewport()
            scroller.evaluate("node => node.scrollTop = 0")
            capture("mobile-replay-dark.png")
            page.keyboard.press("Escape")
            expect(sheet).to_have_count(0)
            expect(dock).to_be_focused()
            assert page.evaluate("document.documentElement.scrollWidth === innerWidth")

            page.get_by_role("button", name="Switch to light theme").click()
            open_session("race", "lookback")
            dock.click()
            expect(
                sheet.get_by_role("table", name="Session classification")
            ).to_be_visible()
            expect(sheet.locator("tbody tr")).to_have_count(len(entries))
            capture("mobile-classification-light.png")

            page.set_viewport_size({"width": 1440, "height": 880})
            open_session("qualifying")
            expect(tower.get_by_role("columnheader", name="Best lap")).to_be_visible()
            expect(tower.get_by_role("button", name="Interval")).to_have_count(0)
            expect(tower.locator("tbody tr[data-position='1']")).to_have_count(0)
            last_lap = max(
                row[0]
                for rows in streams["qualifying"]["timed_laps"].values()
                for row in rows
            )
            seek(page, last_lap - 2000)
            expect(tower.locator("tbody tr[data-position='1']")).to_be_visible()
            tower.scroll_into_view_if_needed()
            capture("desktop-qualifying-light.png")

            open_session("practice", "lookback")
            expect(tower.get_by_role("columnheader", name="Best lap")).to_be_visible()
            open_session("sprint")
            expect(tower.get_by_role("button", name="Interval")).to_be_visible()
            expect(tower.locator("tbody tr")).to_have_count(report["sprint"]["entries"])
            seek(page, streams["sprint"]["race_crossings"][4][0] + 8000)
            expect(tower.get_by_text("Lap 6", exact=True)).to_be_visible()
            if not report["sprint"]["interval_samples"]:
                expect(tower.get_by_text("* Last shared timing line", exact=True)).to_be_visible()
            assert not errors, errors
            browser.close()

        report["browser_checks"] = [
            "Full field with no layout and no drivers selected",
            "Gap to leader and interval",
            "Safety car and lap counter follow seeking and rewinding",
            "One timing request while seeking",
            "Layout change keeps the column choice",
            "Sticky desktop rail and full width on collapse",
            "Mobile sheet, scroll, Escape and focus return",
            "Light and dark themes",
            "Race and sprint running order, qualifying and practice best laps",
        ]
        (artifacts / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
    finally:
        cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    row = db.get(UserRecord, sys.argv[1])
    if row and row.email.startswith('tower-e2e-'):
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
