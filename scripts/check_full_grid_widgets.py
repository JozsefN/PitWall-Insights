"""Exercise full-grid widgets with stored OpenF1 telemetry and timing in Chromium."""
from filter_controls import select_control

import json
import re
import secrets
import subprocess
from time import sleep
from urllib.error import HTTPError
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright

from check_session_review_browser import BASE, ROOT, api

ARTIFACTS = ROOT / "docs/testing/full-grid-widgets"


def chart_geometry(widget, plot, summary=None):
    geometry = widget.evaluate("""(node, [plot, summary]) => {
      const svg = node.querySelector(plot);
      const box = svg.getBoundingClientRect();
      const summaryBox = summary && node.querySelector(summary)?.getBoundingClientRect();
      return {
        height: Math.round(box.height),
        width: Math.round(box.width),
        paintedWidth: Math.round(svg.firstElementChild.getBoundingClientRect().width),
        overlap: !!summaryBox?.height && box.bottom > summaryBox.top + 1,
      };
    }""", [plot, summary])
    assert geometry["height"] >= 176 and geometry["width"] > 0, geometry
    assert geometry["paintedWidth"] >= 0.97 * geometry["width"], geometry
    assert not geometry["overlap"], geometry
    return geometry


def entry_ids(widget, selector):
    return set(widget.locator(selector).evaluate_all("nodes => nodes.map(node => node.dataset.entryId)"))


def visible_plot_fraction(widget, selector):
    return widget.evaluate("""(node, selector) => {
        const card = node.querySelector('.widget-card').getBoundingClientRect();
        const plot = node.querySelector(selector).getBoundingClientRect();
        return (Math.min(card.bottom, plot.bottom) - Math.max(card.top, plot.top)) / plot.height;
    }""", selector)


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    email = f"grid-widgets-{secrets.token_hex(6)}@example.com"
    token = api("POST", "/api/auth/signup", payload={"email": email, "password": secrets.token_urlsafe(24)})["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    report = {}
    try:
        race = api("POST", "/api/sessions/import", token, {
            "season_year": 2025, "round_number": 7, "session_name": "Race",
            "source_session_key": "openf1:session:9987", "import_profile": "core",
        })
        sid = race["id"]
        entries = api("GET", f"/api/sessions/{sid}/entries", token)
        drivers = {entry["id"] for entry in entries}
        assert len(drivers) == 20, len(drivers)
        abbreviations = {str(entry["car_number"]): entry["driver_abbreviation"] for entry in entries}
        assert abbreviations["1"] == "VER" and abbreviations["4"] == "NOR", abbreviations
        assert len(set(abbreviations.values())) == 20, abbreviations
        focus = next(entry["id"] for entry in entries if str(entry["car_number"]) == "4")

        def workspace(mode, layout, lap="all", selected=None):
            return f"{BASE}/sessions/{sid}?" + urlencode({
                "mode": mode, "layout": f"builtin:{layout}", "lap": lap,
                "drivers": ",".join(sorted(drivers if selected is None else selected)),
            })

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="dark")
            page.set_default_timeout(15000)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/login")
            page.evaluate("token => localStorage.setItem('auth_token', token)", token)

            page.goto(workspace("simulation", "replay-command"))
            jump = page.get_by_label("Jump to lap", exact=True)
            start_button = page.get_by_role("button", name="Start", exact=True)
            try:
                expect(start_button).to_be_enabled(timeout=180000)
            except AssertionError as error:
                raise AssertionError(page.locator("#replay-start-status").inner_text()) from error
            select_control(jump, label="Lap 3")
            expect(page.locator(".track-map-viewer__driver-dot")).to_have_count(20, timeout=30000)
            expect(page.locator(".replay-driver-card")).to_have_count(20, timeout=30000)
            cards = page.locator('[data-widget="replay-driver-cards"]')
            expect(cards.locator(".driver-card__speed-path").first).to_be_visible()
            card_height = cards.bounding_box()["height"]
            face = cards.locator(f'.replay-driver-card[data-entry-id="{focus}"]')
            expect(face.locator(".driver-card__meter")).to_be_visible()
            assert next(entry for entry in entries if entry["id"] == focus)["headshot_url"]
            select_control(cards.get_by_label("Drivers", exact=True), focus)
            expect(cards.locator(".replay-driver-card")).to_have_count(1)
            assert cards.bounding_box()["height"] == card_height
            face.screenshot(path=str(ARTIFACTS / "replay-driver-card.png"))
            select_control(cards.get_by_label("Drivers", exact=True), "")
            report["replay_map_and_driver_cards"] = 20
            select_control(jump, label="Lap 16")
            stint = page.locator('[data-widget="stint-analysis"]')
            expect(stint.get_by_role("img", name="Stint analysis chart")).to_be_visible()
            lines = ".stint-chart__line[data-entry-id]"
            assert entry_ids(stint, lines) == drivers
            stint_plot = ".stint-chart__svg"
            report["stint_full_grid"] = chart_geometry(stint, stint_plot, ".stint-summary")
            stint.screenshot(path=str(ARTIFACTS / "replay-stints-full-grid.png"))
            expect(stint.get_by_role("button", name="Trend", exact=True)).to_have_attribute("aria-pressed", "false")
            picker = stint.get_by_label("Drivers", exact=True)
            select_control(picker, focus)
            assert entry_ids(stint, lines) == {focus}
            expect(stint.get_by_role("button", name="Trend", exact=True)).to_have_attribute("aria-pressed", "true")
            summary = stint.locator(".stint-summary__item").filter(has_text="Visible Laps").locator("strong")
            visible_laps = int(summary.inner_text())
            assert 0 < visible_laps <= 15, visible_laps
            stint.get_by_text("Driver and stint visibility", exact=True).click()
            switches = stint.locator(".stint-toggle-row")
            original_height = chart_geometry(stint, stint_plot, ".stint-summary")["height"]
            assert original_height == report["stint_full_grid"]["height"]
            for switch in switches.all():
                switch.click()
                expect(switch).to_have_attribute("aria-pressed", "false")
            expect(summary).to_have_text("0")
            expect(stint.get_by_text("All stints are hidden.", exact=False)).to_be_visible()
            for switch in switches.all():
                switch.click()
            expect(summary).to_have_text(str(visible_laps))
            stint.get_by_text("Driver and stint visibility", exact=True).click()
            select_control(picker, "")
            assert entry_ids(stint, lines) == drivers
            select_control(jump, label="Lap 9")
            page.wait_for_function("""() => {
                const laps = [...document.querySelectorAll('.stint-chart__point title')]
                    .map(title => Number(title.textContent.match(/lap (\\d+):/)[1]));
                return laps.length > 0 && Math.max(...laps) <= 9;
            }""")
            assert chart_geometry(stint, stint_plot, ".stint-summary")["height"] == original_height
            expect(page.locator('.sessions-driver-chip[aria-pressed="true"]')).to_have_count(20)
            page.get_by_role("button", name="Reset", exact=True).click()
            expect(stint.get_by_text("No completed stint laps", exact=False)).to_be_visible()
            expect(cards.locator(".driver-card__speed-path")).to_have_count(0)

            page.goto(workspace("lookback", "stint-strategy", 15))
            expect(stint.get_by_role("img", name="Stint analysis chart")).to_be_visible()
            chart_geometry(stint, stint_plot, ".stint-summary")
            table = page.locator('[data-widget="lap-table"]')
            expect(table.get_by_role("row")).to_have_count(21)
            expect(table.get_by_text("Showing 1–20 of 20 lap entries")).to_be_visible()
            table.screenshot(path=str(ARTIFACTS / "lap-table-full-grid.png"))
            driver_toolbar = page.locator(".sessions-driver-toolbar")
            driver_toolbar.get_by_role("button", name="Clear", exact=True).click()
            expect(stint.get_by_text("Choose drivers", exact=False)).to_be_visible()
            expect(table.get_by_role("row")).to_have_count(0)
            driver_toolbar.get_by_role("button", name="All", exact=True).click()
            expect(page.locator('.sessions-driver-chip[aria-pressed="true"]')).to_have_count(20)
            page.get_by_role("button", name="Lap 15", exact=True).click()
            expect(table.get_by_role("row")).to_have_count(21)

            page.goto(workspace("lookback", "stint-strategy", 63))
            expect(table.get_by_role("table")).to_be_visible()
            late_lap_drivers = table.get_by_role("row").count() - 1
            assert 0 < late_lap_drivers < 20, late_lap_drivers
            report["late_lap_drivers_with_data"] = late_lap_drivers
            page.goto(workspace("lookback", "session-trends"))
            expect(table.get_by_role("row")).to_have_count(25)
            before = table.get_by_role("row").nth(1).inner_text()
            next_page = table.get_by_role("button", name="Next", exact=True)
            next_page.click()
            expect(table.get_by_text(re.compile(r"Showing 25–48 of"))).to_be_visible()
            assert table.get_by_role("row").nth(1).inner_text() != before
            table.get_by_role("button", name="Previous", exact=True).click()
            expect(table.get_by_text(re.compile(r"Showing 1–24 of"))).to_be_visible()
            assert table.get_by_role("row").nth(1).inner_text() == before
            report["single_lap_table_drivers"] = 20

            pace = page.locator('[data-widget="lap-time-trend"]')
            expect(pace.get_by_role("img", name="Lap time comparison chart")).to_be_visible()
            pace_plot = ".lap-pace-chart__svg"
            assert entry_ids(pace, ".lap-pace-chart__line") == drivers
            report["pace_desktop"] = chart_geometry(pace, pace_plot, ".lap-pace-summary")
            select_control(pace.get_by_label("Drivers", exact=True), focus)
            assert entry_ids(pace, ".lap-pace-chart__line") == {focus}
            expect(pace.locator(".lap-pace-chart__reference-line")).to_have_count(1)
            select_control(pace.get_by_label("Drivers", exact=True), "")
            page.get_by_role("button", name="Switch to light theme").click()
            page.set_viewport_size({"width": 390, "height": 844})
            expect(pace).to_have_attribute("data-density", "compact")
            report["pace_mobile"] = chart_geometry(pace, pace_plot, ".lap-pace-summary")
            assert visible_plot_fraction(pace, pace_plot) >= 0.8
            assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
            pace.screenshot(path=str(ARTIFACTS / "lap-pace-mobile-full-grid.png"))
            filters = pace.get_by_role("button", name="Filters & reference", exact=True)
            filters.click()
            expect(pace.get_by_label("Reference", exact=True)).to_be_visible()
            filters.click()
            page.set_viewport_size({"width": 1440, "height": 1000})

            page.goto(workspace("lookback", "compare-lap", 15))
            plots = page.locator(".telemetry-chart__svg")
            expect(plots).to_have_count(3, timeout=180000)
            for plot in plots.all():
                expect(plot.locator("path[data-entry-id]")).to_have_count(20)
                widget = plot.locator("xpath=ancestor::div[@data-widget][1]")
                chart_geometry(widget, ".telemetry-chart__svg")
                assert visible_plot_fraction(widget, ".telemetry-chart__svg") >= 0.85
                picker = widget.get_by_label("Drivers", exact=True)
                select_control(picker, focus)
                expect(plot.locator("path[data-entry-id]")).to_have_count(1)
                expect(plot.locator("path[data-entry-id]")).to_have_attribute("data-entry-id", focus)
                select_control(picker, "")
            report["speed_throttle_brake_traces_per_plot"] = 20
            page.locator(".dashboard-section__body").first.screenshot(path=str(ARTIFACTS / "compare-lap-full-grid.png"))
            missing = f"**/entries/{focus}/telemetry/car?*"
            page.route(missing, lambda route: route.fulfill(
                status=200, json=[], headers={"Access-Control-Allow-Origin": BASE},
            ))
            page.reload()
            expect(plots).to_have_count(3, timeout=30000)
            partial = page.locator('[data-widget="brake-trace-chart"]')
            expect(partial.locator("path[data-entry-id]")).to_have_count(19)
            expect(partial.get_by_text("Samples available for 19 of 20 drivers.")).to_be_visible()
            select_control(partial.get_by_label("Drivers", exact=True), focus)
            expect(partial.get_by_text("No telemetry samples for this driver", exact=False)).to_be_visible()
            select_control(partial.get_by_label("Drivers", exact=True), "")
            expect(partial.locator("path[data-entry-id]")).to_have_count(19)
            report["traces_when_one_driver_has_no_samples"] = 19
            page.unroute(missing)
            page.goto(workspace("lookback", "race-review"))
            tyres = page.locator('[data-widget="tyre-timeline"]')
            positions = page.locator('[data-widget="position-history"]')
            stint_pace = page.locator('[data-widget="stint-performance"]')
            pace_context = page.locator('[data-widget="pace-context"]')
            expect(tyres.locator(".tyre-row")).to_have_count(20)
            expect(positions.locator(".timing-plot__series")).to_have_count(20)
            expect(tyres.get_by_text("Medium", exact=True)).to_be_visible()
            tyres.screenshot(path=str(ARTIFACTS / "tyre-timeline.png"))
            tyre_height = tyres.bounding_box()["height"]
            select_control(tyres.get_by_label("Drivers", exact=True), focus)
            expect(tyres.get_by_role("list", name="Selected driver's tyre sets")).to_be_visible()
            assert tyres.bounding_box()["height"] == tyre_height
            select_control(stint_pace.get_by_label("Stint performance driver", exact=True), focus, timeout=60000)
            expect(stint_pace.locator(".stint-pace-visual")).to_be_visible(timeout=60000)
            expect(pace_context.get_by_role("list", name="Target lap or cohort compared with its reference")).to_be_visible(timeout=30000)
            expect(pace_context.locator(".pace-context-track").first).to_be_visible()
            expect(pace_context.get_by_text("Metrics and evidence", exact=True)).to_be_attached()
            pace_context.locator(".pace-context-visual").evaluate("node => node.scrollIntoView({block: 'center'})")
            pace_context.locator(".pace-context-visual").screenshot(path=str(ARTIFACTS / "pace-context.png"))
            pace_height = stint_pace.bounding_box()["height"]
            stint_pace.get_by_text("Metrics and evidence", exact=True).click()
            expect(stint_pace.locator(".insight-visual-evidence")).to_have_attribute("open", "")
            assert stint_pace.bounding_box()["height"] == pace_height
            stint_pace.get_by_text("Metrics and evidence", exact=True).click()
            stint_pace.screenshot(path=str(ARTIFACTS / "stint-pace.png"))
            select_control(positions.get_by_label("Drivers", exact=True), focus)
            expect(positions.locator('.timing-plot [data-emphasis="true"]')).to_have_count(1)
            positions.screenshot(path=str(ARTIFACTS / "position-history.png"))
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth === innerWidth")
            positions.screenshot(path=str(ARTIFACTS / "position-history-mobile.png"))
            page.set_viewport_size({"width": 1440, "height": 1000})

            page.goto(workspace("simulation", "strategy-desk"))
            jump = page.get_by_label("Jump to lap", exact=True)
            expect(jump.locator("option", has_text="Lap 16")).to_be_attached(timeout=30000)
            select_control(jump, label="Lap 16")
            expect(tyres.locator(".tyre-row__stint").first).to_be_attached()
            expect(positions.locator(".timing-plot__series").first).to_be_attached()
            for widget in (tyres, positions):
                cut = widget.locator("[data-last-lap]").evaluate_all("nodes => nodes.map(node => Number(node.dataset.lastLap))")
                assert cut and max(cut) <= 16, cut
            page.get_by_role("button", name="Reset", exact=True).click()
            expect(positions.locator(".timing-plot__series")).to_have_count(0)
            expect(tyres.locator(".tyre-row__stint")).to_have_count(0)
            report["timing_visuals_follow_replay"] = True

            page.goto(workspace("simulation", "engineering-desk"))
            jump = page.get_by_label("Jump to lap", exact=True)
            expect(jump.locator("option", has_text="Lap 16")).to_be_attached(timeout=30000)
            select_control(jump, label="Lap 16")
            workload = page.locator('[data-widget="tyre-workload"]')
            expect(workload.locator(".insight-context > span").first).to_contain_text(
                re.compile(r"Replay .+ [1-9]\d*:\d{2}"), timeout=60000,
            )
            expect(workload.locator(".snapshot-refresh-status")).to_have_attribute("data-visible", "false", timeout=60000)
            expect(workload.locator('.tyre-load-profile [data-missing="false"]').first).to_be_visible(timeout=60000)
            workload.screenshot(path=str(ARTIFACTS / "tyre-workload.png"))
            report["tyre_profile_and_stint_pace"] = True

            page.goto(BASE + "/dashboard-builder?audience=session-lookback")
            page.get_by_role("button", name="+ New layout", exact=True).click()
            page.get_by_label("Layout name", exact=True).fill("Race timing board")
            search = page.get_by_label("Search widgets", exact=True)
            for name in ("Tyre timeline", "Position history"):
                search.fill(name)
                page.get_by_role("button", name=f"Add {name}", exact=True).click()
            expect(page.get_by_test_id("editor-widget")).to_have_count(2)
            page.get_by_role("button", name="Save layout", exact=True).click()
            expect(page.locator(".builder-layout-card").filter(has_text="Race timing board")).to_be_visible()
            page.goto(workspace("lookback", "session-trends"))
            page.get_by_role("button", name="Race timing board", exact=True).click()
            expect(tyres.locator(".tyre-row")).to_have_count(20)
            expect(positions.locator(".timing-plot__series")).to_have_count(20)
            report["new_panels_work_in_saved_dashboard"] = True
            assert not errors, errors
            browser.close()

        for attempt in range(4):
            try:
                review = api("POST", f"/api/feature-metrics/sessions/{sid}/review", token, {
                    "entry_ids": sorted(drivers), "groups": ["pace", "pit", "racecraft"],
                })
                break
            except HTTPError as error:
                if error.code != 429 or attempt == 3:
                    raise
                sleep(int(error.headers.get("Retry-After", "2")))
        assert set(review["entry_ids"]) == drivers
        assert set(review["groups"]) == {"pace", "pit", "racecraft"}
        report["pace_pit_racecraft_api_selection"] = 20
        (ARTIFACTS / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    row = db.get(UserRecord, sys.argv[1])
    if row and row.email.startswith('grid-widgets-'):
        db.delete(row)
        db.commit()
"""
        subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", cleanup, owner], cwd=ROOT / "backend", check=True)


if __name__ == "__main__":
    main()
