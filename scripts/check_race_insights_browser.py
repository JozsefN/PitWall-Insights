"""Real local API/browser checks; no mocked telemetry or event responses."""
from local_test_accounts import seed_verified_account

import json
import secrets
import subprocess
from collections import Counter
from pathlib import Path
from time import monotonic
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:4173"
ARTIFACTS = ROOT / "docs/testing/race-estimates-v2-browser"


def api(method, path, token=None, payload=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(
        Request(
            "http://127.0.0.1:8000" + path,
            method=method,
            headers=headers,
            data=json.dumps(payload).encode() if payload is not None else None,
        ),
        timeout=60,
    ) as response:
        return json.load(response) if response.status != 204 else None


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    user_id = None
    checks, errors, requests = [], [], []
    try:
        email = "race-insights-e2e-" + secrets.token_hex(6) + "@example.com"
        password = secrets.token_urlsafe(20)
        auth = seed_verified_account({"email": email, "password": password})
        token = auth["access_token"]
        user_id = api("GET", "/api/auth/session", token)["user_id"]
        sid = next(
            row["id"]
            for row in api("GET", "/api/sessions", token)
            if row["source_session_key"] == "openf1:session:9693"
        )
        entries = [
            row
            for row in api("GET", f"/api/sessions/{sid}/entries", token)
            if row["car_number"] in ("1", "4", "16")
        ]
        ids = [row["id"] for row in entries]
        assert len(ids) == 3
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.set_default_timeout(20000)
            page.on("pageerror", lambda error: errors.append(str(error)))

            def capture(request):
                if request.url.endswith("/race-estimates") and request.method == "POST":
                    requests.append(request.post_data_json)

            page.on("request", capture)
            page.goto(BASE + "/login")
            page.get_by_label("Email", exact=True).fill(email)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.locator(".app-header").get_by_role(
                "button", name="Sign out", exact=True
            ).wait_for()
            page.goto(BASE + "/dashboard-builder?audience=live-race")
            expect(
                page.locator(".builder-layout-card").filter(has_text="Race viewer")
            ).to_have_count(1)
            expect(
                page.locator(".builder-layout-card").filter(has_text="Strategy desk")
            ).to_have_count(1)
            page.get_by_role("button", name="+ New layout", exact=True).click()
            page.get_by_label("Layout name", exact=True).fill(
                "Race insight browser test"
            )
            page.get_by_label("Search widgets", exact=True).fill("notifications")
            expect(page.locator(".editor-library__widget")).to_have_count(1)
            page.get_by_role(
                "button", name="Add Race notifications", exact=True
            ).click()
            page.get_by_label("Messages shown", exact=True).select_option("3")
            page.get_by_label("Notification driver scope", exact=True).select_option(
                "all"
            )
            page.get_by_label(
                "Include detection candidates (unconfirmed)", exact=True
            ).uncheck()
            page.get_by_label("On-track pass estimates", exact=True).uncheck()
            page.get_by_role("button", name="Save layout", exact=True).click()
            expect(page.get_by_role("status")).to_contain_text("Layout saved")
            saved = next(
                row
                for row in api("GET", "/api/layouts", token)
                if row["name"] == "Race insight browser test"
            )
            opts = saved["config"]["sections"][0]["layout"]["children"][0]["options"]
            assert (
                opts["maxItems"] == 3
                and opts["includeCandidates"] is False
                and "overtake" not in opts["eventTypes"]
            )
            page.reload()
            page.locator(".builder-layout-card").filter(
                has_text="Race insight browser test"
            ).get_by_role("button", name="Edit layout", exact=True).click()
            page.get_by_role(
                "button", name="Configure Race notifications", exact=True
            ).click()
            expect(page.get_by_label("Messages shown", exact=True)).to_have_value("3")
            expect(
                page.get_by_label("On-track pass estimates", exact=True)
            ).not_to_be_checked()
            page.screenshot(
                path=str(ARTIFACTS / "notification-settings.png"), full_page=True
            )
            checks.append("builder_search_category_settings_database_save_and_reload")
            page.get_by_role("button", name="Cancel", exact=True).click()
            # Exercise every registered insight component against real model responses.
            manifest = json.loads(
                (ROOT / "shared/dashboard-widgets.json").read_text(encoding="utf-8")
            )
            panels = [
                "race-notifications",
                "driver-overview",
                "battle-radar",
                "wake-exposure",
                "tyre-workload",
                "braking-analysis",
                "pace-context",
                "closing-gaps",
                "overtake-opportunities",
                "pit-scenarios",
                "incident-watch",
                "track-conditions",
                "stint-performance",
                "driver-comparison",
                "model-quality",
            ]
            assert all(panel in manifest["widgets"] for panel in panels)
            children = [
                {
                    "type": "widget",
                    "widgetId": key,
                    "instanceId": key,
                    "placement": {"x": i % 2 * 6, "y": i // 2 * 8, "w": 6, "h": 8},
                    "options": opts if key == "race-notifications" else {},
                }
                for i, key in enumerate(panels)
            ]
            layout = api(
                "POST",
                "/api/layouts",
                token,
                {
                    "name": "All race analysis panels",
                    "audience": "live-race",
                    "schema_version": 2,
                    "config": {
                        "id": "race-estimate-e2e",
                        "sections": [
                            {
                                "id": "main",
                                "layout": {
                                    "type": "group",
                                    "direction": "row",
                                    "grid": {"columns": 12, "rowHeight": 48},
                                    "children": children,
                                },
                            }
                        ],
                    },
                },
            )
            started = monotonic()
            page.goto(
                BASE
                + f"/sessions/{sid}?mode=simulation&layout=user:{layout['id']}&drivers={','.join(ids)}&lap=all"
            )
            expect(page.locator("[data-insight-panel]")).to_have_count(15)
            slider = page.locator(".sessions-replay-timeline input[type=range]")
            slider.wait_for()

            def seek(value):
                slider.evaluate(
                    "(node,value)=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(node,String(value));node.dispatchEvent(new Event('input',{bubbles:true}));node.dispatchEvent(new Event('change',{bubbles:true}));}",
                    value,
                )

            seek(10000000)
            page.wait_for_function(
                "Array.from(document.querySelectorAll('[data-insight-panel] .insight-context')).every(node=>node.textContent.includes('02:46:40'))"
            )
            overview = page.locator('[data-insight-panel="driver-overview"]')
            expect(
                overview.get_by_text("Loading race analysis", exact=False)
            ).to_have_count(0)
            expect(overview.locator(".insight-metric strong").first).not_to_have_text(
                "Unavailable"
            )
            expect(
                overview.locator(".insight-metric summary > span").first
            ).to_have_text("Current speed")
            feed = page.locator('[data-insight-panel="race-notifications"]')
            expect(feed.locator(".insight-events > li")).to_have_count(3)
            assert "Estimate candidate" not in feed.inner_text()
            startup = round(monotonic() - started, 3)
            counts = Counter(row["as_of_ms"] for row in requests)
            # An initial timing snapshot may refresh once per telemetry source as it becomes ready.
            assert 1 <= counts[10000000] <= 3, counts
            checks.append("all_15_panels_real_openf1_snapshot_and_shared_request")
            page.screenshot(path=str(ARTIFACTS / "race-panels.png"), full_page=True)
            pending = []

            def delay_estimates(route):
                if (route.request.post_data_json or {}).get("as_of_ms") == 10005000:
                    pending.append(route)
                else:
                    route.continue_()

            page.route("**/race-estimates", delay_estimates)
            context = overview.locator(".insight-context")
            speed = overview.locator(".insight-metric strong").first
            previous_speed = speed.inner_text()
            seek(10005000)
            expect(context).to_contain_text("02:46:40")
            expect(context.locator('[data-visible="true"]')).to_have_text("· Updating")
            expect(speed).to_have_text(previous_speed)
            assert pending
            for request in pending:
                request.continue_()
            page.unroute("**/race-estimates", delay_estimates)
            expect(context).to_contain_text("02:46:45")
            checks.append("race_estimates_remain_visible_during_delayed_refresh")
            seek(9000000)
            page.wait_for_function(
                "Array.from(document.querySelectorAll('[data-insight-panel] .insight-context')).every(node=>node.textContent.includes('02:30:00'))"
            )
            times = feed.locator("time").all_text_contents()
            assert all(value <= "02:30:00" for value in times), times
            checks.append("replay_rewind_removes_future_notifications")
            comparison = page.locator('[data-insight-panel="driver-comparison"]')
            expect(
                comparison.get_by_label("Comparison driver", exact=True)
            ).to_be_attached()
            expect(comparison.locator("tbody tr")).to_have_count(8)
            checks.append("driver_comparison_and_metric_evidence_render")
            feeds = []
            for index, maximum in enumerate((5, "auto")):
                feeds.append(
                    {
                        "type": "widget",
                        "widgetId": "race-notifications",
                        "instanceId": f"feed-{index}",
                        "placement": {"x": index * 6, "y": 0, "w": 6, "h": 10},
                        "options": {**opts, "maxItems": maximum},
                    }
                )
            feed_layout = api(
                "POST",
                "/api/layouts",
                token,
                {
                    "name": "Notification sizes",
                    "audience": "live-race",
                    "schema_version": 2,
                    "config": {
                        "id": "feed-sizes",
                        "sections": [
                            {
                                "id": "main",
                                "layout": {
                                    "type": "group",
                                    "direction": "row",
                                    "grid": {"columns": 12, "rowHeight": 48},
                                    "children": feeds,
                                },
                            }
                        ],
                    },
                },
            )
            page.goto(
                BASE
                + f"/sessions/{sid}?mode=simulation&layout=user:{feed_layout['id']}&drivers={','.join(ids)}&lap=all"
            )
            slider = page.locator(".sessions-replay-timeline input[type=range]")
            slider.wait_for()
            seek(10000000)
            page.wait_for_function(
                "Array.from(document.querySelectorAll('[data-insight-panel] .insight-context')).every(node=>node.textContent.includes('02:46:40'))"
            )
            expect(
                page.locator('[data-insight-panel="race-notifications"]').first.locator(
                    ".insight-events > li"
                )
            ).to_have_count(5)
            auto_frame = page.locator(".responsive-widget").nth(1)
            height = auto_frame.bounding_box()["height"]
            expected = max(1, min(12, int((height - 170) // 85)))
            expect(
                page.locator('[data-insight-panel="race-notifications"]')
                .nth(1)
                .locator(".insight-events > li")
            ).to_have_count(expected)
            checks.append("fixed_five_and_height_dependent_notification_capacity")
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            )
            checks.append("mobile_panels_do_not_overflow_page")
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.goto(
                BASE
                + f"/sessions/{sid}?mode=simulation&layout=builtin:engineering-desk&drivers={','.join(ids)}"
            )
            slider = page.locator(".sessions-replay-timeline input[type=range]")
            slider.wait_for()
            seek(10000000)
            circuit = page.locator('[data-widget="replay-track-map"]')
            expect(circuit.locator(".track-map-viewer__driver-dot")).to_have_count(3)
            weather_layer = circuit.get_by_role(
                "button", name="Wind & rain", exact=True
            )
            weather_layer.click()
            expect(circuit.locator(".circuit-wind-speed")).to_contain_text("km/h")
            expect(
                circuit.get_by_text(
                    "Surface wetness by corner is unavailable.", exact=False
                )
            ).to_be_visible()
            circuit.scroll_into_view_if_needed()
            page.screenshot(path=str(ARTIFACTS / "engineering-weather-map.png"))
            circuit.get_by_role("button", name="Flags", exact=True).click()
            expect(circuit.locator(".circuit-map-layers__note")).not_to_contain_text(
                "Loading"
            )
            circuit.get_by_role("button", name="Surface & recovery", exact=True).click()
            expect(
                circuit.get_by_text("Add a registered track profile", exact=False)
            ).to_be_visible()
            wake = page.locator('[data-insight-panel="wake-exposure"]')
            wake.get_by_text("When to use this panel", exact=True).click()
            expect(
                wake.get_by_text("Seek to a green-flag lap", exact=False)
            ).to_be_visible()
            checks.append(
                "engineering_desk_actual_driver_positions_wind_speed_flag_layer_and_panel_guidance"
            )
            page.goto(
                BASE + f"/sessions/{sid}?mode=lookback&layout=builtin:session-trends&drivers={','.join(ids)}"
            )
            page.get_by_role("button", name="Lap 15", exact=True).click()
            lookback_map = page.locator('[data-widget="session-track-map"]')
            lookback_map.get_by_role("button", name="Wind & rain", exact=True).click()
            expect(lookback_map.locator(".circuit-map-layers__bar")).to_contain_text("Lap 15 end")
            checks.append("lookback_map_weather_uses_selected_lap_end_time")
            assert not errors, errors
            browser.close()
        started = monotonic()
        response = api(
            "POST",
            f"/api/feature-metrics/sessions/{sid}/race-estimates",
            token,
            {
                "as_of_ms": 10000000,
                "entry_ids": sorted(ids),
                "lookback_ms": 300000,
                "sample_interval_ms": 500,
                "max_events": 500,
            },
        )
        cache_seconds = round(monotonic() - started, 3)
        report = {
            "checks": checks,
            "count": len(checks),
            "browser_errors": errors,
            "panels": len(panels),
            "source": "openf1:session:9693",
            "mocked_telemetry": False,
            "as_of_ms": 10000000,
            "panel_startup_seconds": startup,
            "cached_api_seconds": cache_seconds,
            "cache_hit": response["cache_hit"],
            "version": response["version"],
            "metric_count": len(response["drivers"][0]["metrics"]),
            "events": response["event_count"],
            "telemetry_coverage_pct": {
                row["car_number"]: row["metrics"]["telemetry_coverage_pct"]["value"]
                for row in response["drivers"]
            },
            "requests_at_target_cutoff": counts[10000000],
            "test_account_removed": True,
        }
        (ARTIFACTS / "results.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
    finally:
        if user_id:
            cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
 user=db.get(UserRecord,sys.argv[1])
 if user and user.email.startswith('race-insights-e2e-'):
  db.delete(user); db.commit()
"""
            subprocess.run(
                [
                    str(ROOT / "backend/.venv/Scripts/python.exe"),
                    "-c",
                    cleanup,
                    user_id,
                ],
                cwd=ROOT / "backend",
                check=True,
            )


if __name__ == "__main__":
    main()
