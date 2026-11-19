"""Check every filter in built-in layouts and editor settings against local data.

Requires the API on :8000, Vite on :5173, Playwright, and the stored 2025
Bahrain race/practice, Australian qualifying and a sprint session.
Creates and removes its own test profile; does not save layouts or import data.
"""
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright
from check_session_review_browser import api

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("PITWALL_FRONTEND_URL", "http://localhost:5173")
ARTIFACTS = ROOT / "docs/testing/filter-controls"

CONTRAST = """(node) => {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
  const context = canvas.getContext('2d', {willReadFrequently: true});
  function rgba(value) {
    context.clearRect(0, 0, 1, 1); context.fillStyle = value; context.fillRect(0, 0, 1, 1);
    return [...context.getImageData(0, 0, 1, 1).data];
  }
  function blend(front, back) {
    return front.slice(0, 3).map((channel, i) => channel * front[3] / 255 + back[i] * (1 - front[3] / 255));
  }
  function luminance(channels) {
    const c = channels.map(x => x / 255).map(x => x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4);
    return c[0] * .2126 + c[1] * .7152 + c[2] * .0722;
  }
  const style = getComputedStyle(node);
  const layers = []; let parent = node;
  while (parent) { layers.push(rgba(getComputedStyle(parent).backgroundColor)); parent = parent.parentElement; }
  const bg = layers.reverse().reduce((back, front) => blend(front, back), [255, 255, 255]);
  const a = luminance(blend(rgba(style.color), bg)), b = luminance(bg);
  return { text: node.textContent.trim(), color: style.color, background: bg,
    ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05) };
}"""


def name_of(control):
    return control.evaluate("""node => {
      if (node.getAttribute('aria-label')) return node.getAttribute('aria-label');
      const label = node.labels?.[0]?.cloneNode(true);
      label?.querySelectorAll('select, .driver-select').forEach(child => child.remove());
      return label?.textContent.trim().replace(/\\s+/g, ' ') || node.id;
    }""")


def check_contrast(control):
    result = control.evaluate(CONTRAST)
    assert result["ratio"] >= 4.5, result
    return result


def native_filters(page, coverage, context):
    for control in page.locator("select").all():
        if not control.is_visible():
            continue
        name = name_of(control)
        check_contrast(control)
        options = control.locator("option")
        for option in options.all():
            check_contrast(option)
        coverage.add(name)
        if control.is_enabled() and name != "Jump to lap":
            original = control.input_value()
            alternative = control.locator("option:not(:disabled)").evaluate_all(
                "nodes => nodes.map(node => node.value)"
            )
            alternative = next((value for value in alternative if value != original), None)
            if alternative is not None:
                control.select_option(alternative)
                expect(control).to_have_value(alternative)
                if original in options.evaluate_all("nodes => nodes.map(node => node.value)"):
                    control.select_option(original)
    print(f"native: {context}", flush=True)


def driver_filters(page, coverage, context, screenshot=False):
    page.locator(".driver-select").evaluate_all("nodes => nodes.forEach((node, index) => node.dataset.filterAuditId = String(index))")
    for index in range(page.locator(".driver-select").count()):
        control = page.locator(f'.driver-select[data-filter-audit-id="{index}"]')
        if not control.count():
            continue
        if not control.is_visible() or not control.is_enabled():
            continue
        control.scroll_into_view_if_needed()
        name = name_of(control)
        widget = control.evaluate("node => node.closest('[data-widget]')?.dataset.widget || ''")
        coverage.add(f"{widget}: {name}")
        check_contrast(control)
        original = control.get_attribute("title")
        control.click()
        popup = page.get_by_role("listbox", name=name, exact=True)
        expect(popup).to_be_visible()
        for option in popup.get_by_role("option").all():
            check_contrast(option)
            badge = option.locator(".driver-select__badge")
            if badge.count():
                check_contrast(badge)
                assert len(badge.inner_text()) == 3, badge.inner_text()
                assert option.locator(".driver-select__number").inner_text().startswith("#")
                assert option.locator(".driver-select__name").inner_text().strip()
        box = popup.bounding_box()
        viewport = page.viewport_size
        assert box["x"] >= 0 and box["y"] >= 0, box
        assert box["x"] + box["width"] <= viewport["width"] + 1, box
        assert box["y"] + box["height"] <= viewport["height"] + 1, box
        if screenshot:
            page.screenshot(path=str(ARTIFACTS / f"{context.replace(':', '-')}-{index}.png"))
        # Keyboard navigation must scroll the last entry into the visible menu.
        control.press("End")
        last = popup.get_by_role("option").last
        expect(last).to_have_attribute("data-active", "true")
        last_box = last.bounding_box()
        assert last_box["y"] + last_box["height"] <= box["y"] + box["height"] + 1
        control.press("Home")
        expect(popup.get_by_role("option").first).to_have_attribute("data-active", "true")
        control.press("Escape")
        expect(control).to_have_attribute("aria-expanded", "false")
        expect(control).to_be_focused()
        assert control.get_attribute("title") == original
        # Commit a different option and confirm that reopening marks it selected.
        control.click()
        choices = popup.get_by_role("option")
        alternative = next((option for option in choices.all() if option.get_attribute("aria-selected") != "true"), None)
        if alternative is not None:
            target = alternative.get_attribute("aria-label")
            alternative.click()
            expect(control).to_have_attribute("title", target)
            control.click()
            expect(popup.get_by_role("option", name=target, exact=True)).to_have_attribute("aria-selected", "true")
            if original:
                previous = popup.get_by_role("option", name=original, exact=True)
                if previous.count():
                    previous.click()
                else:
                    control.press("Escape")
            else:
                control.press("Escape")
        else:
            control.press("Escape")
        control.click()
        control.press("Tab")
        expect(control).to_have_attribute("aria-expanded", "false")
    print(f"drivers: {context}", flush=True)


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    email = f"filter-e2e-{secrets.token_hex(6)}@example.com"
    token = api("POST", "/api/auth/signup", payload={"email": email, "password": secrets.token_urlsafe(24)})["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    report = {"complete": False, "native_filters": set(), "driver_filters": set(), "layouts": [], "errors": [],
              "fixtures": ["Telemetry readiness is forced ready; telemetry and timing rows come from stored sessions.",
                           "A synthetic damage report exercises the conditional repair-time selector.",
                           "A transient, unsaved layout displays every insights panel."]}
    if "--resume" in sys.argv and (ARTIFACTS / "results.json").exists():
        previous = json.loads((ARTIFACTS / "results.json").read_text(encoding="utf-8"))
        for key in ["native_filters", "driver_filters"]:
            report[key].update(previous[key])
        report["layouts"] = previous["layouts"]
        if "rival-pit-scenarios: Rival for pit scenarios" not in report["driver_filters"]:
            report["layouts"] = [layout for layout in report["layouts"] if layout != "builtin:race-strategy"]
    try:
        stored = api("GET", "/api/sessions", token)
        sessions = {
            "race": next(s for s in stored if s["season_year"] == 2025 and s["round_number"] == 7 and s["session_name"] == "Race" and s["source_session_key"].startswith("openf1:")),
            "review_race": next(s for s in stored if s["season_year"] == 2025 and s["round_number"] == 4 and s["session_name"] == "Race"),
            "practice": next(s for s in stored if s["season_year"] == 2024 and s["round_number"] == 12 and s["session_name"] == "Practice 1"),
            "qualifying": next(s for s in stored if s["season_year"] == 2026 and s["round_number"] == 3 and s["session_name"] == "Qualifying"),
            "sprint": next(s for s in stored if s["session_name"] == "Sprint"),
        }
        entries = {kind: api("GET", f"/api/sessions/{session['id']}/entries", token) for kind, session in sessions.items()}
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="dark")
            page.set_default_timeout(15000)
            page.on("dialog", lambda dialog: dialog.accept())
            page.on("pageerror", lambda error: report["errors"].append(str(error)))
            page.route("**/api/telemetry/materialization/ensure", lambda route: route.fulfill(json={"ready": True, "job_id": None, "segments": []}))
            def damage_case(route):
                response = route.fetch()
                data = response.json()
                incidents = data.get("groups", {}).get("incidents")
                if incidents is not None:
                    incidents["reports"].append({"kind": "damage_report", "entry_ids": [],
                                                "time_ms": data["as_of_ms"], "message": "Filter control test fixture", "lap_number": None})
                route.fulfill(response=response, json=data)
            page.route("**/api/feature-metrics/sessions/*/review", damage_case)
            page.goto(BASE + "/login")
            page.evaluate("token => localStorage.setItem('auth_token', token)", token)
            layouts = page.evaluate("""async () => {
              const { builtinSessionLayouts } = await import('/src/widgets/registry/dashboard.config.ts');
              return builtinSessionLayouts.map(layout => ({id: layout.id, kind: layout.config.sessionKind || 'race',
                mode: layout.audience === 'live-race' ? 'simulation' : 'lookback'}));
            }""")
            audit_layout = page.evaluate("""async () => {
              const { insightPanels } = await import('/src/widgets/insights/panel-specs.ts');
              return {id: 'filter-audit', name: 'Filter audit', source: 'user', audience: 'live-race', schemaVersion: 1,
                createdAt: '2026-11-19T00:00:00Z', updatedAt: '2026-11-19T00:00:00Z', description: 'Unsaved browser test fixture',
                config: {id: 'filter-audit', title: 'Filter audit', sessionKind: 'race', sections: [{id: 'panels',
                  layout: {type: 'group', direction: 'column', gap: 20, children: Object.keys(insightPanels).map(widgetId =>
                    ({type: 'widget', widgetId, width: 'full', height: 'lg', minHeight: 440}))}}]}};
            }""")
            page.route("**/api/layouts", lambda route: route.fulfill(json=[audit_layout]) if route.request.method == "GET" else route.continue_())
            layouts.append({"id": "user:filter-audit", "kind": "race", "mode": "simulation"})
            for layout in layouts:
                if layout["id"] in report["layouts"]:
                    continue
                kind = "review_race" if layout["id"] in {"builtin:race-strategy", "builtin:race-strategy-review"} else layout["kind"]
                session = sessions[kind]
                url = BASE + f"/sessions/{session['id']}?" + urlencode({
                    "layout": layout["id"], "mode": layout["mode"],
                    "lap": 15 if kind in {"race", "practice"} else "all",
                    "drivers": ",".join(entry["id"] for entry in entries[kind]),
                })
                page.goto(url)
                expect(page.locator(".widget-card").first).to_be_visible(timeout=60000)
                if layout["mode"] == "simulation":
                    jump = page.get_by_label("Jump to lap", exact=True)
                    expect(jump).to_be_enabled(timeout=60000)
                    jump.select_option(index=min(25, jump.locator("option").count() - 1))
                    if layout["id"] == "builtin:race-strategy":
                        page.get_by_role("slider", name="Replay time").evaluate("""node => {
                          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(node,'9500000');
                          node.dispatchEvent(new Event('input',{bubbles:true})); node.dispatchEvent(new Event('change',{bubbles:true}));
                        }""")
                        expect(page.get_by_label("Rival for pit scenarios", exact=True)).to_be_visible(timeout=60000)
                # Wait for the API-backed selectors as well as the static toolbar.
                page.wait_for_function("""() => ![...document.querySelectorAll('.widget-card')].some(node =>
                    /Loading session review|Loading context|Loading team radio/.test(node.textContent))""", timeout=90000)
                page.wait_for_timeout(500)
                for widget_id in ["session-track-map", "replay-track-map"]:
                    widget = page.locator(f'[data-widget="{widget_id}"]')
                    if widget.count():
                        expect(widget.get_by_label("Focus", exact=True)).to_be_visible(timeout=90000)
                for widget_id in ["telemetry-line-chart", "brake-trace-chart"]:
                    widget = page.locator(f'[data-widget="{widget_id}"]')
                    for panel in widget.all():
                        expect(panel.get_by_label("Drivers", exact=True)).to_be_visible(timeout=90000)
                for theme, width in [("dark", 1440), ("light", 1440), ("dark", 390), ("light", 390)]:
                    page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
                    page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
                    # Compact charts reveal the reference selector behind their filters toggle.
                    for toggle in page.get_by_role("button", name="Filters & reference", exact=True).all():
                        if toggle.is_visible() and toggle.get_attribute("aria-expanded") != "true":
                            toggle.click()
                    context = f"{layout['id']}:{theme}:{width}"
                    native_filters(page, report["native_filters"], context)
                    driver_filters(page, report["driver_filters"], context,
                                   screenshot=layout["id"] == "builtin:replay-command" and theme == "dark")
                report["layouts"].append(layout["id"])

            page.goto(BASE + "/sessions?view=explorer")
            expect(page.locator("select").first).to_be_visible()
            for theme in ["dark", "light"]:
                page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
                native_filters(page, report["native_filters"], f"explorer:{theme}")
            page.goto(BASE + "/dashboard-builder")
            page.set_viewport_size({"width": 1440, "height": 1000})
            expect(page.locator("#builder-source")).to_be_visible()
            native_filters(page, report["native_filters"], "layout-library")
            page.get_by_role("button", name="+ New layout", exact=True).click()
            for theme in ["dark", "light"]:
                page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
                native_filters(page, report["native_filters"], f"layout-editor:{theme}")
            page.get_by_role("button", name="Cancel", exact=True).click()
            # These three settings panels cover all conditional native controls.
            for title, mode in [("Telemetry Line Chart", "session-lookback"), ("Race notifications", "live-race"), ("Session Track Map", "session-lookback")]:
                page.get_by_role("button", name="+ New layout", exact=True).click()
                page.get_by_label("Layout mode", exact=True).select_option(mode)
                search = page.get_by_label("Search widgets", exact=True)
                search.fill(title)
                add = page.get_by_role("button", name=f"Add {title}", exact=True)
                expect(add).to_be_enabled()
                add.click()
                for theme in ["dark", "light"]:
                    page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
                    native_filters(page, report["native_filters"], f"panel-settings:{title}:{theme}")
                page.get_by_role("button", name="Cancel", exact=True).click()
            assert not report["errors"], report["errors"]
            required_native = {"Season", "Race weekend", "Show", "Layout mode", "Session type", "Widget access", "Metric",
                               "Messages shown", "Notification driver scope", "Minimum severity", "Trailing window", "Default map layer",
                               "Jump to lap", "Qualifying timed lap", "Projection horizon", "Extra repair time scenario", "Rival action"}
            assert required_native <= report["native_filters"], required_native - report["native_filters"]
            required_drivers = {"session-track-map: Focus", "replay-track-map: Focus", "lap-time-trend: Reference",
                                "telemetry-line-chart: Drivers", "brake-trace-chart: Drivers", "stint-analysis: Drivers",
                                "replay-driver-cards: Drivers", "tyre-timeline: Drivers", "position-history: Drivers",
                                "qualifying-lap-map: Qualifying lap driver", "lap-segment-review: Focus lap", "lap-segment-review: Comparison lap",
                                "race-pace-forecast: Focus projected driver", "pit-benchmark: Pit rejoin driver",
                                "rival-comparison: Rival comparison driver", "rival-pit-scenarios: Rival for pit scenarios"}
            assert required_drivers <= report["driver_filters"], required_drivers - report["driver_filters"]
            browser.close()
        from check_driver_select import main as keyboard_and_touch_checks
        keyboard_and_touch_checks()
        report["keyboard_and_touch"] = "passed in light and dark themes, including disabled and empty lists"
        report["complete"] = True
    finally:
        code = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
 user=db.get(UserRecord,sys.argv[1])
 if user and user.email.startswith('filter-e2e-'):
  db.delete(user)
  db.commit()
"""
        subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", code, owner], cwd=ROOT / "backend", check=True)
        for key in ["native_filters", "driver_filters"]:
            report[key] = sorted(report[key])
        (ARTIFACTS / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
