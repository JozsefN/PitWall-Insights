"""Check Melbourne's telemetry-aligned road and pit overlay with archived race data."""
from local_test_accounts import seed_verified_account
from filter_controls import select_control

import json
import secrets
import subprocess
from urllib.parse import parse_qs, urlencode, urlsplit

from playwright.sync_api import expect, sync_playwright

from check_session_review_browser import BASE, ROOT, api

ARTIFACTS = ROOT / "docs/testing/qualifying-lap-map"


def load_without_reports(session_id):
    code = """import json
import sys
from unittest.mock import patch
from modules.session_domain.infrastructure.pit_map import load_pit_map
from modules.storage.infrastructure.db import SessionLocal
with SessionLocal() as db, patch(
    'modules.session_domain.infrastructure.pit_map._pit_reports', return_value=[]
):
    print(json.dumps(load_pit_map(db, sys.argv[1])))
"""
    result = subprocess.check_output(
        [str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", code, session_id],
        cwd=ROOT / "backend",
    )
    return json.loads(result)


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    email = f"circuit-pit-e2e-{secrets.token_hex(6)}@example.com"
    token = seed_verified_account({"email": email, "password": secrets.token_urlsafe(24)})["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    try:
        sid = next(row["id"] for row in api("GET", "/api/sessions", token) if row["source_session_key"] == "openf1:session:9693")
        pit_path = f"/api/sessions/{sid}/pit-map"
        before = api("GET", pit_path, token)
        assert len(before["lane"]) >= 30 and before["reported_visits"] >= 1
        assert before["lane_source"] == "pit_reports"
        fallback = load_without_reports(sid)
        assert fallback["lane_source"] == "position_traces"
        assert fallback["reported_visits"] == 0 and len(fallback["lane"]) >= 30
        assert len({visit["entry_id"] for visit in fallback["visits"]}) >= 2
        entries = api("GET", f"/api/sessions/{sid}/entries", token)
        grid_first = sorted(entries, key=lambda row: (row["grid_position"] or float("inf"), int(row["car_number"])))[:3]

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="dark")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/login")
            page.evaluate("token => localStorage.setItem('auth_token', token)", token)
            page.goto(BASE + f"/sessions/{sid}?" + urlencode({"mode": "simulation", "layout": "builtin:race-spectator", "drivers": ",".join(row["id"] for row in grid_first)}))
            panel = page.locator('[data-widget="replay-track-map"]')
            lane = panel.locator(".track-map-pits__lane")
            expect(lane).to_be_visible(timeout=180000)
            expect(lane).to_have_attribute("data-source", "pit_reports")
            expect(panel.get_by_text("Mapped centreline with estimated width.", exact=False)).to_be_visible()
            expect(panel.get_by_role("button", name="Pit lane", exact=True)).to_have_count(0)
            expect(panel.get_by_role("button", name="Prepare field pit traces", exact=True)).to_have_count(0)
            path = lane.get_attribute("d")
            for layer in ("Wind & rain", "Flags", "Surface & recovery", "Track"):
                panel.get_by_role("button", name=layer, exact=True).click()
                expect(lane).to_be_visible()
                expect(lane).to_have_attribute("d", path)
            panel.screenshot(path=str(ARTIFACTS / "melbourne-pit-lane-overview.png"))
            focus = panel.get_by_role("combobox", name="Focus", exact=True)
            select_control(focus, label="Pit lane")
            expect(panel.locator(".track-map-pits__box")).to_have_count(0)
            after = api("GET", pit_path, token)
            assert len(after["lane"]) >= 30 and len(after["boxes"]) >= 8, (len(after["lane"]), len(after["boxes"]))
            assert len(after["visits"]) >= len(before["visits"])
            slider = page.get_by_role("slider", name="Replay time", exact=True)
            slider.focus()
            page.keyboard.press("End")
            expect(panel.locator(".track-map-pits__box")).to_have_count(len(after["boxes"]))
            panel.screenshot(path=str(ARTIFACTS / "melbourne-pit-lane.png"))
            page.get_by_role("button", name="Reset", exact=True).click()
            expect(panel.locator(".track-map-pits__box")).to_have_count(0)

            bounds = api("GET", f"/api/sessions/{sid}/replay-timeline", token)
            position_queries = []
            def record_position(request):
                url = urlsplit(request.url)
                if url.path.startswith(f"/api/sessions/{sid}/entries/") and url.path.endswith("/telemetry/position"):
                    position_queries.append(parse_qs(url.query))

            page.on("request", record_position)
            lookback = urlencode({
                "mode": "lookback", "layout": "builtin:session-trends",
                "drivers": ",".join(row["id"] for row in grid_first),
            })
            page.goto(BASE + f"/sessions/{sid}?{lookback}")
            panel = page.locator('[data-widget="session-track-map"]')
            expect(panel.get_by_text("Mapped centreline with estimated width.", exact=False)).to_be_visible(timeout=180000)
            expect(panel.locator(".track-map-pits__lane")).to_be_visible()
            expect(panel.locator(".track-map-viewer__racing-line")).to_have_count(len(grid_first))
            assert len(position_queries) >= len(grid_first), position_queries
            for query in position_queries:
                assert query["session_time_from_ms"] == [str(bounds["start_time_ms"])], query
                assert query["session_time_to_ms"] == [str(bounds["end_time_ms"])], query
                assert int(query["sample_interval_ms"][0]) >= 500 and "lap_number" not in query, query
            reference_ids = list(dict.fromkeys(visit["entry_id"] for visit in fallback["visits"]))[:2]
            requested = []
            def record_preparation(request):
                if request.method == "POST" and request.url.endswith("/telemetry/materialization/ensure"):
                    payload = request.post_data_json
                    if payload["kinds"] == ["position"] and set(payload["entry_ids"]) == set(reference_ids):
                        requested.append(payload)
            page.on("request", record_preparation)

            def provide_fallback(route):
                data = fallback if requested else {
                    "reported_visits": 0, "lane_source": None, "lane": [], "boxes": [], "visits": [],
                    "reference_entry_ids": reference_ids,
                }
                route.fulfill(json=data, headers={"Access-Control-Allow-Origin": "*"})

            page.route("**" + pit_path, provide_fallback)
            page.reload()
            inferred = panel.locator(".track-map-pits__lane")
            expect(inferred).to_be_visible(timeout=180000)
            expect(inferred).to_have_attribute("data-source", "position_traces")
            assert len(requested) == 1 and requested[0]["scope"] == "session", requested
            assert inferred.evaluate("node => getComputedStyle(node).strokeDasharray !== 'none'")
            select_control(panel.get_by_role("combobox", name="Focus", exact=True), label="Pit lane")
            panel.screenshot(path=str(ARTIFACTS / "melbourne-pit-lane-inferred.png"))
            assert not errors, errors
            browser.close()

        report = {"circuit": "Melbourne", "session_key": 9693, "reported_visits": after["reported_visits"],
                  "mapped_visits": len(after["visits"]), "team_boxes": len(after["boxes"]),
                  "before_preparation_boxes": len(before["boxes"]), "lane_points": len(after["lane"]),
                  "lookback_sampled_driver_requests": len(position_queries),
                  "fallback_without_reports": {"lane_points": len(fallback["lane"]), "matched_visits": len(fallback["visits"])}}
        (ARTIFACTS / "melbourne-pit-map-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    row = db.get(UserRecord, sys.argv[1])
    if row and row.email.startswith('circuit-pit-e2e-'):
        db.delete(row)
        db.commit()
"""
        subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", cleanup, owner], cwd=ROOT / "backend", check=True)


if __name__ == "__main__":
    main()
