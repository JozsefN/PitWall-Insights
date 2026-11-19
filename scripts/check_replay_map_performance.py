"""Measure real full-grid replay on a saved race and exercise the Imola close-up fixture."""
from filter_controls import select_control

import json
import os
import re
import secrets
import subprocess
from urllib.parse import urlencode

from playwright.sync_api import expect, sync_playwright

from check_session_review_browser import BASE, ROOT, api
from check_workspace_usability import contrast

ARTIFACTS = ROOT / "docs/testing/replay-map"
STAGE = os.environ.get("PITWALL_REPLAY_CHECK", "current")
SESSION_KEY = os.environ.get("PITWALL_REPLAY_SESSION", "9987")


def measure(page, speed):
    page.get_by_role("button", name=f"{speed}x", exact=True).click()
    slider = page.get_by_role("slider", name="Replay time")
    initial = int(slider.input_value())
    start = page.get_by_role("button", name="Start", exact=True)
    expect(start).to_be_enabled(timeout=60_000)
    start.click()
    report = page.evaluate("""async () => {
      const intervals = [];
      const tasks = [];
      const observer = new PerformanceObserver(list => tasks.push(...list.getEntries().map(entry => entry.duration)));
      observer.observe({entryTypes: ['longtask']});
      const started = performance.now();
      let last;
      await new Promise(resolve => {
        function frame(now) {
          if (last !== undefined) intervals.push(now - last);
          last = now;
          if (now - started < 6000) requestAnimationFrame(frame);
          else resolve();
        }
        requestAnimationFrame(frame);
      });
      observer.disconnect();
      const elapsed = performance.now() - started;
      const sorted = [...intervals].sort((a, b) => a - b);
      return {elapsed_ms: elapsed, frame_p95_ms: sorted[Math.floor(sorted.length * .95)],
        longest_frame_ms: sorted.at(-1), frames_over_50_ms: intervals.filter(ms => ms > 50).length,
        long_tasks: tasks.length};
    }""")
    advanced = int(slider.input_value()) - initial
    page.get_by_role("button", name="Pause", exact=True).click()
    report["simulated_ms"] = advanced
    report["clock_ratio"] = round(advanced / (speed * report["elapsed_ms"]), 3)
    return report


def screenshot_wind(panel, name):
    motion = panel.locator(".circuit-wind-field__arrows")
    motion.evaluate("""node => node.getAnimations().forEach(animation => {
        animation.pause();
        animation.currentTime = animation.effect.getComputedTiming().duration / 2;
    })""")
    panel.screenshot(path=str(ARTIFACTS / name))


def check_car_scale(panel):
    expect(panel.locator(".track-map-viewer__scale")).to_be_visible()
    marker = panel.locator(".track-map-car").first
    expect(marker).to_be_visible()
    dimensions = marker.evaluate("""node => {
      const surface = node.closest('.track-map-viewer__surface');
      const scale = surface.querySelector('.track-map-viewer__scale');
      const metresPerPixel = Number.parseFloat(scale.querySelector('span').textContent)
        / scale.querySelector('i').getBoundingClientRect().width;
      const matrix = node.getScreenCTM();
      const body = node.getBBox();
      const lengthPx = body.width * Math.hypot(matrix.a, matrix.b);
      const widthPx = body.height * Math.hypot(matrix.c, matrix.d);
      return {
        length_m: lengthPx * metresPerPixel,
        width_m: widthPx * metresPerPixel,
        length_px: lengthPx,
      };
    }""")
    assert abs(dimensions["length_m"] - 5.5) < .06, dimensions
    assert abs(dimensions["width_m"] - 2) < .03, dimensions
    return dimensions


def seek(page, time_ms):
    slider = page.get_by_role("slider", name="Replay time")
    slider.evaluate("""(node, time) => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(node, String(time));
      node.dispatchEvent(new Event('input', {bubbles: true}));
    }""", time_ms)
    expect(slider).to_have_value(str(time_ms))


def check_pit_lane(page, panel, entries, pits):
    assert len(pits["lane"]) >= 30 and len(pits["boxes"]) == 10, pits
    norris = next(entry for entry in entries if entry["car_number"] == "4")
    stop = next(visit for visit in pits["visits"] if visit["entry_id"] == norris["id"] and visit["stopped_from_ms"])
    focus = panel.get_by_role("combobox", name="Focus", exact=True)
    lane = panel.locator(".track-map-pits__lane")
    expect(lane).to_have_count(1)
    assert lane.evaluate("node => getComputedStyle(node).stroke !== 'none'")
    boxes = panel.locator(".track-map-pits__box")
    fit = panel.get_by_role("button", name="Reset view", exact=True)
    car = panel.locator(f'[data-track-driver="{norris["id"]}"]')

    select_control(focus, label="Pit lane")
    start = int(page.get_by_role("slider", name="Replay time").get_attribute("min"))
    seek(page, start)
    expect(boxes).to_have_count(0)
    seek(page, stop["start_ms"] + 3300)
    expect(car).to_have_attribute("data-pit-phase", "lane")
    seek(page, (stop["stopped_from_ms"] + stop["stopped_until_ms"]) // 2 + 1200)
    expect(car).to_have_attribute("data-pit-phase", "box")
    seek(page, stop["stopped_until_ms"] + 3500)
    expect(car).to_have_attribute("data-pit-phase", "lane")
    seek(page, stop["end_ms"] + 3500)
    expect(car).not_to_have_attribute("data-pit-phase", re.compile(".+"))

    last_box = max(box["known_at_ms"] for box in pits["boxes"])
    seek(page, last_box + 100)
    expect(boxes).to_have_count(10)
    assert len({box.get_attribute("fill") for box in boxes.all()}) >= 8
    expect(panel.get_by_text("Pit lane and team markers are estimated from recorded stops.")).to_be_visible()
    panel.scroll_into_view_if_needed()
    panel.screenshot(path=str(ARTIFACTS / "imola-pit-lane.png"))
    fit.click()
    select_control(page.get_by_label("Jump to lap", exact=True), label="Lap 3")
    return {"team_boxes": len(pits["boxes"]), "visits": len(pits["visits"]), "lane_points": len(pits["lane"])}


def check_map_controls(page, panel, entries, throttle):
    canvas = panel.get_by_label("Top-down track map", exact=True)
    focus = panel.get_by_role("combobox", name="Focus", exact=True)
    fit = panel.get_by_role("button", name="Reset view", exact=True)
    initial_view = canvas.get_attribute("viewBox")
    expect(focus).to_have_attribute("data-value", "pack")
    expect(panel.locator(".track-map-viewer__driver-label-chip")).to_have_count(0)

    # A close observation of the two McLarens in a completed green-flag lap.
    # This fixture checks display and labels, not physical wheel-to-wheel accuracy.
    slider = page.get_by_role("slider", name="Replay time")
    slider.evaluate("""node => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(node, '12456889');
      node.dispatchEvent(new Event('input', {bubbles: true}));
    }""")
    expect(slider).to_have_value("12456889")
    norris = next(entry for entry in entries if entry["car_number"] == "4")
    piastri = next(entry for entry in entries if entry["car_number"] == "81")
    select_control(focus, norris["id"])
    zoom = panel.get_by_role("button", name="Zoom in", exact=True)
    for _ in range(10):
        if panel.get_by_text("1800% zoom", exact=True).is_visible():
            break
        zoom.click()
    expect(panel.get_by_text("1800% zoom", exact=True)).to_be_visible()
    original_zoom_scale = check_car_scale(panel)
    zoom.click()
    zoom.click()
    expect(zoom).to_be_disabled()
    road = panel.locator(".track-map-viewer__illustrated-road")
    expect(road).to_have_count(1)
    expect(panel.locator(".track-map-viewer__track-center")).to_have_count(0)
    road_path = road.get_attribute("d")
    assert " C " in road_path and road_path.count(" Z") == 2
    edges = [
        [tuple(float(value) for value in command.split()[-2:]) for command in re.split(r"[MC]", edge) if command.strip()]
        for edge in road_path.split(" Z") if edge.strip()
    ]
    road_widths = [((bx - ax) ** 2 + (by - ay) ** 2) ** .5 / 10 for (ax, ay), (bx, by) in zip(*edges, strict=True)]
    assert 10.99 <= min(road_widths) <= max(road_widths) <= 15.01, (min(road_widths), max(road_widths))
    scale_at_maximum_zoom = check_car_scale(panel)
    assert scale_at_maximum_zoom["length_px"] >= 2 * original_zoom_scale["length_px"] - .05
    panel.get_by_role("button", name="Zoom out", exact=True).click()
    scale_at_previous_zoom = check_car_scale(panel)
    zoom.click()
    for driver in (norris, piastri):
        label = panel.locator(f'[data-entry-id="{driver["id"]}"]')
        expect(label).to_have_text(driver["driver_name"])
        assert label.evaluate("node => Number(node.querySelector('rect').getAttribute('y')) < Number(node.querySelector('line').getAttribute('y1'))")
    panel.scroll_into_view_if_needed()
    panel.screenshot(path=str(ARTIFACTS / "imola-close-up-dark.png"))

    close_view = canvas.get_attribute("viewBox")
    box = canvas.bounding_box()
    assert box
    x = box["x"] + box["width"] * 0.52
    y = box["y"] + box["height"] * 0.48
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 38, y + 37, steps=6)
    page.mouse.up()
    expect(canvas).not_to_have_attribute("viewBox", close_view)
    expect(focus).to_have_attribute("data-value", "manual")
    fit.click()
    expect(canvas).to_have_attribute("viewBox", initial_view)
    expect(panel.locator(".track-map-viewer__track-center")).to_be_visible()

    compact_style = page.add_style_tag(content="""
      .track-map-viewer .track-map-viewer__surface { width: min(438px, 100%); height: 150px; flex: none; }
      .track-map-viewer .track-map-viewer__svg { height: 150px; min-height: 150px; }
    """)
    max_entry = next(entry for entry in entries if entry["car_number"] == "1")
    select_control(focus, max_entry["id"])
    for _ in range(10):
        if zoom.is_disabled():
            break
        zoom.click()
    expect(zoom).to_be_disabled()
    expect(canvas).to_have_css("height", "150px")
    expect(panel.locator(".track-map-viewer__scale span")).to_have_text("10 m")
    compact_scale = check_car_scale(panel)
    assert 40 <= compact_scale["length_px"] <= 44, compact_scale
    max_label = panel.locator(f'[data-entry-id="{max_entry["id"]}"]')
    expect(max_label).to_have_text(max_entry["driver_name"])
    panel.locator(".track-map-viewer__surface").screenshot(path=str(ARTIFACTS / "imola-compact-close-up.png"))
    compact_style.evaluate("node => node.remove()")
    fit.click()

    panel.get_by_role("button", name="Wind & rain", exact=True).click()
    expect(panel.locator(".circuit-wind-speed")).to_have_text(re.compile(r"^\d+(\.\d+)? km/h$"), timeout=45_000)
    wind = panel.locator(".circuit-wind-field")
    expect(wind).to_have_attribute("data-bearing", re.compile(r"^\d+(\.\d+)?$"))
    motion = wind.locator(".circuit-wind-field__arrows")
    expect(motion.locator("span")).to_have_count(28)
    transform = motion.evaluate("node => getComputedStyle(node).transform")
    page.wait_for_function("previous => getComputedStyle(document.querySelector('.circuit-wind-field__arrows')).transform !== previous", arg=transform)
    assert wind.evaluate("node => getComputedStyle(node).pointerEvents") == "none"
    expect(panel.get_by_text("Circuit-wide weather.", exact=False)).to_be_visible()
    expect(canvas).to_have_attribute("viewBox", initial_view)
    throttle.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    wind_playback = measure(page, 5)
    throttle.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    assert wind_playback["frame_p95_ms"] <= 55, wind_playback
    assert .90 <= wind_playback["clock_ratio"] <= 1.10, wind_playback
    page.emulate_media(reduced_motion="reduce")
    assert motion.evaluate("node => getComputedStyle(node).animationName") == "none"
    page.emulate_media(reduced_motion="no-preference")
    panel.scroll_into_view_if_needed()
    screenshot_wind(panel, "imola-wind-dark.png")

    page.get_by_role("button", name="Switch to light theme").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    panel.scroll_into_view_if_needed()
    note = panel.locator(".circuit-map-layers__note").last
    assert note.evaluate("node => parseFloat(getComputedStyle(node).fontSize)") >= 13
    assert contrast(note) >= 7
    screenshot_wind(panel, "imola-wind-light.png")
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    expect(canvas).to_be_visible()
    panel.scroll_into_view_if_needed()
    screenshot_wind(panel, "imola-wind-phone.png")
    return {
        "wind_5x": wind_playback,
        "car_scale": {
            "original_zoom": original_zoom_scale,
            "maximum_zoom": scale_at_maximum_zoom,
            "previous_zoom": scale_at_previous_zoom,
            "compact_close_up": compact_scale,
        },
        "illustrated_road_metres": {"narrowest": round(min(road_widths), 2), "widest": round(max(road_widths), 2)},
    }


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    account = f"replay-map-check-{secrets.token_hex(6)}@example.com"
    token = api("POST", "/api/auth/signup", payload={"email": account, "password": secrets.token_urlsafe(24)})["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    try:
        imola_fixture = SESSION_KEY == "9987"
        if imola_fixture:
            race = api("POST", "/api/sessions/import", token, {
                "season_year": 2025, "round_number": 7, "session_name": "Race",
                "source_session_key": "openf1:session:9987", "import_profile": "core",
            })
        else:
            race = next(row for row in api("GET", "/api/sessions", token)
                        if row["source_session_key"] == f"openf1:session:{SESSION_KEY}" and row["session_name"] == "Race")
        sid = race["id"]
        entries = api("GET", f"/api/sessions/{sid}/entries", token)
        assert len(entries) >= 18
        with sync_playwright() as browser_tools:
            browser = browser_tools.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="dark")
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script(f"localStorage.setItem('auth_token', {json.dumps(token)});")
            params = urlencode({"mode": "simulation", "layout": "builtin:engineering-desk", "drivers": ",".join(entry["id"] for entry in entries)})
            page.goto(f"{BASE}/sessions/{sid}?{params}")
            start = page.get_by_role("button", name="Start", exact=True)
            expect(start).to_be_enabled(timeout=180_000)
            select_control(page.get_by_label("Jump to lap", exact=True), label="Lap 3")
            expect(start).to_be_enabled(timeout=120_000)
            map_panel = page.locator('[data-widget="replay-track-map"]')
            dots = map_panel.locator(".track-map-viewer__driver-dot")
            expect(dots.first).to_be_visible()
            if imola_fixture:
                expect(dots).to_have_count(len(entries))
            pit_checks = None
            if STAGE != "before":
                expect(map_panel.get_by_text(re.compile(r"Mapped (centreline with estimated width|road edges)\."))).to_be_visible()
                if imola_fixture:
                    pits = api("GET", f"/api/sessions/{sid}/pit-map", token)
                    pit_checks = check_pit_lane(page, map_panel, entries, pits)
            map_panel.scroll_into_view_if_needed()
            artifact = STAGE if imola_fixture else f"{STAGE}-{SESSION_KEY}"
            chart = "imola-grid" if imola_fixture else "race-grid"
            map_panel.screenshot(path=str(ARTIFACTS / f"{artifact}-{chart}.png"))
            path = map_panel.locator('.track-map-viewer__track-center').get_attribute('d')
            active_drivers = dots.count()
            throttle = page.context.new_cdp_session(page)
            throttle.send("Emulation.setCPUThrottlingRate", {"rate": 4})
            results = {"event": race["event_name"], "session_key": SESSION_KEY, "selected_drivers": len(entries),
                       "active_drivers": active_drivers, "closed_outline": path.rstrip().endswith("Z"),
                       "pit_map": pit_checks, "1x": measure(page, 1), "5x": measure(page, 5), "errors": errors}
            throttle.send("Emulation.setCPUThrottlingRate", {"rate": 1})
            if STAGE != "before":
                assert results["closed_outline"], "A partial trace cannot serve as a circuit outline"
                for speed in ("1x", "5x"):
                    stats = results[speed]
                    assert stats["frame_p95_ms"] <= 55, stats
                    assert .90 <= stats["clock_ratio"] <= 1.10, stats
                if imola_fixture:
                    try:
                        results.update(check_map_controls(page, map_panel, entries, throttle))
                        results["workflows"] = ["stable whole-circuit camera", "two named close-up cars", "fixed car dimensions at expanded zoom", "readable car in a compact map", "smooth closed road without a reference line", "max zoom, pan, reset", "moving wind arrows, km/h and reduced motion", "readable light mode at desktop and phone widths"]
                    except Exception:
                        map_panel.screenshot(path=str(ARTIFACTS / "map-workflow-failure.png"))
                        raise
                assert not errors, errors
            print(json.dumps(results, indent=2), flush=True)
            (ARTIFACTS / f"{artifact}-performance.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
            browser.close()
    finally:
        cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    row = db.get(UserRecord, sys.argv[1])
    if row and row.email.startswith('replay-map-check-'):
        db.delete(row)
        db.commit()
"""
        subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", cleanup, owner], cwd=ROOT / "backend", check=True)


if __name__ == "__main__":
    main()
