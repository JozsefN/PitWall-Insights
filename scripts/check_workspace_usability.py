"""Browser workflow and visual checks using a fresh viewer account and real OpenF1 data."""

import json
import re
import secrets
import subprocess
from time import monotonic

from playwright.sync_api import expect, sync_playwright

from check_session_review_browser import BASE, ROOT, api

ARTIFACTS = ROOT / "docs/testing/visual-hierarchy"


def contrast(locator):
    return locator.evaluate("""node => {
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 1;
      const ctx = canvas.getContext('2d');
      const rgba = value => {
        ctx.clearRect(0, 0, 1, 1);
        ctx.fillStyle = value;
        ctx.fillRect(0, 0, 1, 1);
        return [...ctx.getImageData(0, 0, 1, 1).data];
      };
      const luminance = channels => channels.slice(0, 3).reduce((total, value, index) => {
        const channel = value / 255;
        return total + [0.2126, 0.7152, 0.0722][index] *
          (channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4);
      }, 0);
      const layers = [];
      for (let target = node; target; target = target.parentElement) {
        const fill = rgba(getComputedStyle(target).backgroundColor);
        layers.push(fill);
        if (fill[3] === 255) break;
      }
      const blend = (base, color) => base.map((channel, i) =>
        channel + (color[i] - channel) * color[3] / 255);
      const background = layers.reverse().reduce(blend, [255, 255, 255]);
      const text = luminance(blend(background, rgba(getComputedStyle(node).color)));
      const surface = luminance(background);
      return (Math.max(text, surface) + .05) / (Math.min(text, surface) + .05);
    }""")


def screenshot(page, name):
    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    page.screenshot(path=str(ARTIFACTS / name), full_page=True, animations="disabled")


def assert_page_fits(page):
    dimensions = page.evaluate("""() => ({width: innerWidth, page: document.documentElement.scrollWidth,
        elements: [...document.querySelectorAll('main *')].filter(node => {
          const rect = node.getBoundingClientRect();
          return rect.right > innerWidth && rect.left < innerWidth;
        }).slice(0, 12).map(node => node.getAttribute('class') || node.tagName)})""")
    assert dimensions["page"] <= dimensions["width"], dimensions


def inject_error(route, status, detail):
    if route.request.method != "POST":
        route.continue_()
        return
    route.fulfill(status=status, json={"detail": detail}, headers={"Access-Control-Allow-Origin": BASE})


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    email = f"viewer-e2e-{secrets.token_hex(6)}@example.com"
    password = secrets.token_urlsafe(20)
    token = api("POST", "/api/auth/signup", payload={"email": email, "password": password})["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    checks, errors, ratios = [], [], {}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="dark")
            page.set_default_timeout(20000)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/dashboard-builder")
            expect(page.get_by_role("button", name="+ New layout", exact=True)).to_have_count(0)
            page.keyboard.press("Tab")
            expect(page.get_by_role("link", name="Skip to content", exact=True)).to_be_focused()
            checks.append("Guest access and keyboard skip link")

            page.goto(BASE + "/login")
            page.get_by_label("Email", exact=True).fill(email)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.get_by_role("link", name="Open profile")).to_be_visible()
            expect(page.get_by_role("heading", name="PitWall Insights", exact=True)).to_be_visible()
            assert_page_fits(page)
            screenshot(page, "00-home-dark.png")
            page.get_by_role("navigation", name="Main navigation").get_by_role("link", name="Sessions", exact=True).click()
            page.get_by_label("Season", exact=True).select_option("2025")
            weekend = page.get_by_label("Race weekend", exact=True)
            option = weekend.locator("option").filter(has_text="Australian Grand Prix")
            weekend.select_option(option.get_attribute("value"))
            page.locator(".sessions-catalog").get_by_role("button", name=re.compile(r"^Race\s")).click()
            mode = page.get_by_role("group", name="Session mode")
            expect(mode.get_by_text("Review completed laps", exact=True)).to_be_visible()
            mode.get_by_role("button", name="Replay", exact=True).click()
            expect(mode.get_by_role("button", name="Replay", exact=True)).to_have_attribute("aria-pressed", "true")
            screenshot(page, "01-session-picker-dark.png")

            import_path = "**/api/sessions/import"
            page.route(import_path, lambda route: inject_error(route, 502, {"message": "Race data is temporarily unavailable. Try again in a moment."}))
            load = page.get_by_role("button", name="Load session", exact=True)
            load.click()
            expect(page.get_by_text("Race data is temporarily unavailable.", exact=False)).to_be_visible()
            expect(load).to_be_enabled()
            screenshot(page, "02-import-retry.png")
            page.unroute(import_path)
            load.click()
            page.wait_for_url(re.compile(r"/sessions/[a-f0-9-]+\?"), timeout=90000)
            sid = page.url.split("/sessions/")[1].split("?")[0]
            checks.append("Real session selection and retry after a simulated upstream failure")

            viewer = page.get_by_role("button", name="Race viewer", exact=True)
            radio_requests = []
            page.on("request", lambda request: radio_requests.append(request.url)
                    if request.url.endswith(f"/sessions/{sid}/radio-timeline") else None)
            round_mark = page.locator(".sessions-workspace__round")
            expect(round_mark).to_have_text("01")
            expect(round_mark).to_have_attribute("aria-hidden", "true")
            expect(page.locator(".sessions-layout-item").first.get_by_text("Start here", exact=True)).to_be_visible()
            expect(page.get_by_text("Follow cars, race updates and radio.", exact=True)).to_be_visible()
            start = page.get_by_role("button", name="Start", exact=True)
            expect(start).to_be_disabled()
            expect(page.locator("#replay-start-status")).to_contain_text("Choose a compatible replay layout")
            timeline = page.get_by_role("slider", name="Replay time")

            def seek(time_ms):
                timeline.evaluate("""(node, time) => {
                    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(node, String(time));
                    node.dispatchEvent(new Event('input', {bubbles: true}));
                }""", time_ms)

            start_requested_at = monotonic()
            viewer.click()
            selected_drivers = page.locator('.sessions-driver-chip[aria-pressed="true"]')
            expect(selected_drivers).to_have_count(3)
            expect(selected_drivers.first.locator(".sessions-driver-chip__number")).to_have_attribute("aria-hidden", "true")
            assert selected_drivers.first.evaluate("node => getComputedStyle(node).borderInlineStartWidth === '4px'")
            assert selected_drivers.first.evaluate("node => node.style.getPropertyValue('--driver-color') !== ''")
            try:
                expect(start).to_be_enabled(timeout=180000)
            except AssertionError as error:
                screenshot(page, "replay-start-blocked.png")
                raise AssertionError(page.locator("#replay-start-status").inner_text()) from error
            startup = round(monotonic() - start_requested_at, 3)
            before = int(timeline.input_value())
            radio = page.locator('[data-review-panel="team-radio"]')
            expect(page.get_by_label("Elapsed replay time")).to_have_text("0:00")
            expect(radio.get_by_text("Radio clips appear here as the race unfolds.")).to_be_visible()
            expect(radio.get_by_role("list", name="Team radio clips")).to_have_count(0)
            start.click()
            page.wait_for_function("start => Number(document.querySelector('[aria-label=\"Replay time\"]').value) > start + 300", arg=before)
            page.get_by_role("button", name="Pause", exact=True).click()
            lap_jump = page.get_by_label("Jump to lap", exact=True)
            lap_jump.select_option(label="Lap 15")
            expect(lap_jump.locator("option:checked")).to_have_text("Lap 15")
            assert int(timeline.input_value()) > before
            seek(10000000)
            estimated = radio.locator("li[data-radio-time-ms]").filter(has_text="≈").first
            expect(estimated).to_be_visible()
            stamp = int(estimated.get_attribute("data-radio-time-ms"))
            clip = radio.locator(f'li[data-radio-time-ms="{stamp}"]').filter(has_text="≈").first
            seek(stamp - 1)
            expect(clip).to_have_count(0)
            seek(stamp)
            expect(clip).to_be_visible()
            expect(clip.locator("time")).to_have_attribute("title", re.compile("Estimated recording time.*Feed time"))
            seek(stamp - 1)
            expect(clip).to_have_count(0)
            seek(10000000)
            progress = timeline.evaluate("node => parseFloat(node.style.getPropertyValue('--replay-fill'))")
            assert 0 < progress < 100, progress
            map_panel = page.locator('[data-widget="replay-track-map"]')
            expect(map_panel.locator(".track-map-viewer__driver-dot")).to_have_count(3)
            expect(page.get_by_role("heading", name="Race updates", exact=True)).to_be_visible()
            expect(page.get_by_role("heading", name="Team radio", exact=True)).to_be_visible()
            play_radio = radio.get_by_role("button", name=re.compile(r"^Play .+ radio at \d+:\d\d")).first
            expect(play_radio).to_be_enabled()
            number = radio.locator(".team-radio-list__number").first
            expect(number).to_have_text(re.compile(r"^#\d+$"))
            assert number.evaluate("node => node.closest('li').style.getPropertyValue('--radio-team') !== ''")
            play_radio.click()
            page.wait_for_function("""() => {
              const audio = document.querySelector('[data-review-panel="team-radio"] audio');
              return audio && !audio.paused && audio.currentTime > 0.15;
            }""", timeout=25000)
            radio.get_by_role("button", name=re.compile(r"^Pause .+ radio at")).click()
            expect(radio.locator("audio")).to_have_js_property("paused", True)
            radio.scroll_into_view_if_needed()
            radio.screenshot(path=str(ARTIFACTS / "team-radio-replay.png"))
            page.get_by_role("button", name="Reset", exact=True).click()
            expect(page.get_by_label("Elapsed replay time")).to_have_text("0:00")
            expect(radio.get_by_role("list", name="Team radio clips")).to_have_count(0)
            expect(radio.locator("audio")).not_to_have_attribute("src", re.compile(r".+"))
            seek(10000000)
            expect(play_radio).to_be_enabled()
            assert len(radio_requests) == 1, radio_requests
            expect(page.get_by_role("heading", name="Wake & traffic", exact=True)).to_have_count(0)
            expect(start).to_be_enabled()
            checks.append("Beginner layout opens with three drivers, working playback, lap jump, race updates and radio")
            checks.append("Replay starts at 0:00, reveals team-coloured radio clips, plays and pauses real audio, and removes clips on reset")
            checks.append("A real archive clip appears at its estimated timestamp and hides on rewind without refetching the timeline")

            for theme in ("dark", "light"):
                if theme == "light":
                    page.get_by_role("button", name="Switch to light theme").click()
                expect(page.locator("html")).to_have_attribute("data-theme", theme)
                expect(viewer).to_have_attribute("aria-pressed", "true")
                expect(timeline).to_have_value("10000000")
                assert_page_fits(page)
                page.evaluate("""async () => {
                    document.documentElement.getBoundingClientRect();
                    await Promise.allSettled(document.getAnimations()
                      .filter(animation => animation instanceof CSSTransition)
                      .map(animation => animation.finished));
                }""")
                samples = {
                    "session title": page.locator(".feature-banner__title"),
                    "primary action": start,
                    "driver name": selected_drivers.first.locator("strong"),
                    "driver team": selected_drivers.first.locator("small"),
                    "mode label": page.locator(".sessions-mode-option strong").first,
                    "viewer purpose": viewer.locator("p"),
                    "recommended label": viewer.locator(".layout-guide-label"),
                }
                ratios[theme] = {key: round(contrast(node), 2) for key, node in samples.items()}
                assert min(ratios[theme].values()) >= 4.5, ratios[theme]
                screenshot(page, f"03-race-viewer-{theme}.png")
            checks.append("Dark and light themes preserve view and meet sampled text contrast")

            page.get_by_role("link", name="Jump to dashboard", exact=False).click()
            expect(page).to_have_url(re.compile(r"#session-dashboard$"))
            expect(page.locator("#session-dashboard")).to_be_focused()
            expect(timeline).to_have_value("10000000")
            checks.append("Direct dashboard navigation keeps the selected replay time")

            for width in (320, 390, 768):
                page.set_viewport_size({"width": width, "height": 844})
                assert_page_fits(page)
                expect(selected_drivers.first.locator("strong")).to_be_visible()
                nav = page.get_by_role("navigation", name="Main navigation")
                assert nav.evaluate("nav => [...nav.querySelectorAll('a')].every(link => link.getBoundingClientRect().right <= innerWidth)")
            page.set_viewport_size({"width": 390, "height": 844})
            screenshot(page, "04-race-viewer-mobile.png")
            checks.append("Viewer layout fits narrow mobile, phone and tablet widths")

            page.get_by_role("button", name="Clear", exact=True).click()
            expect(start).to_be_disabled()
            expect(page.locator("#replay-start-status")).to_contain_text("Choose at least one driver")
            viewer.click()
            expect(selected_drivers).to_have_count(3)
            page.get_by_role("button", name="Favorite Race viewer", exact=True).click()
            expect(page.get_by_role("button", name="Unfavorite Race viewer", exact=True)).to_be_visible()
            page.reload()
            expect(page.locator("html")).to_have_attribute("data-theme", "light")
            expect(page.get_by_role("button", name="Unfavorite Race viewer", exact=True)).to_be_visible()
            expect(selected_drivers).to_have_count(3)
            checks.append("Clearing and restoring the starter drivers, favourites and theme persistence")

            page.set_viewport_size({"width": 1440, "height": 1000})
            page.goto(BASE + f"/sessions/{sid}?mode=simulation&layout=builtin:qualifying-review")
            expect(page.get_by_text("Qualifying review cannot open here.", exact=True)).to_be_visible()
            expect(start).to_be_disabled()
            expect(map_panel).to_have_count(0)
            page.locator(".sessions-layout-heading").get_by_role("link", name="Dashboard Builder").click()
            expect(page.get_by_role("heading", name="Dashboard Builder", exact=True)).to_be_visible()
            screenshot(page, "05-builder-library-light.png")
            page.get_by_role("button", name="+ New layout", exact=True).click()
            page.get_by_label("Layout name", exact=True).fill("My first weather view")
            page.get_by_label("Search widgets", exact=True).fill("Rain & wind history")
            page.get_by_role("button", name="Add Rain & wind history", exact=True).click()
            save = page.get_by_role("button", name="Save layout", exact=True)
            save_path = "**/api/layouts"
            page.route(save_path, lambda route: inject_error(route, 503, "Saving is temporarily unavailable. Try again."))
            save.click()
            expect(page.get_by_role("alert").filter(has_text="Saving is temporarily unavailable")).to_be_visible()
            expect(page.get_by_label("Layout name", exact=True)).to_have_value("My first weather view")
            expect(page.get_by_test_id("editor-widget")).to_have_count(1)
            screenshot(page, "06-builder-save-error-light.png")
            page.unroute(save_path)
            save.click()
            expect(page.locator(".builder-layout-card").filter(has_text="My first weather view")).to_be_visible()
            checks.append("Incompatible direct link is blocked and a failed layout save keeps the complete editable draft")

            page.set_viewport_size({"width": 390, "height": 844})
            assert_page_fits(page)
            expect(page.get_by_role("button", name="+ New layout", exact=True)).to_be_visible()
            page.get_by_role("button", name="Switch to dark theme").click()
            screenshot(page, "07-builder-mobile-dark.png")
            page.get_by_role("button", name="Switch to light theme").click()
            page.set_viewport_size({"width": 1440, "height": 1000})
            checks.append("Builder library remains readable and its New layout control visible on a phone")

            page.get_by_role("link", name="Open profile").click()
            expect(page.get_by_role("heading", name="Your profile", exact=True)).to_be_visible()
            expect(page.locator("html")).to_have_attribute("data-theme", "light")
            assert_page_fits(page)
            screenshot(page, "08-profile-light.png")
            checks.append("Theme follows navigation into the profile")
            assert not errors, errors
            browser.close()
    finally:
        cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    row = db.get(UserRecord, sys.argv[1])
    if row and row.email.startswith('viewer-e2e-'):
        db.delete(row)
        db.commit()
"""
        subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", cleanup, owner], cwd=ROOT / "backend", check=True)

    result = {"checks": checks, "cached_viewer_ready_seconds": startup, "sampled_text_contrast": ratios, "browser_errors": errors}
    (ARTIFACTS / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
