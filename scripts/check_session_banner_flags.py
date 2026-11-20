"""Check the host flag artwork on real saved sessions and narrow screens."""
from local_test_accounts import seed_verified_account

import json
import secrets
import subprocess
from datetime import date
from io import BytesIO
from urllib.parse import urlencode, urlsplit

from PIL import Image
from playwright.sync_api import expect, sync_playwright

from check_session_review_browser import BASE, ROOT, api

ARTIFACTS = ROOT / "docs/testing/session-banner-flags"
CATALOG = json.loads((ROOT / "shared/circuit-catalog.json").read_text(encoding="utf-8"))
FLAG_CODES = list(CATALOG["hosts"])


def check_calendar(token):
    venues = {str(row["openf1Key"]): row for row in CATALOG["circuits"]}
    seasons = {}
    races = []
    for year in range(2023, date.today().year + 1):
        calendar = api("GET", f"/api/sessions/catalog?season={year}", token)
        season_races = [
            row for row in calendar if row["session_name"] == "Race"
            and row["unavailable_reason"] != "This session was cancelled."
        ]
        assert season_races, year
        seasons[year] = len(season_races)
        races.extend(season_races)
    for race in races:
        venue = venues.get(race["circuit_key"])
        assert venue, (race["season_year"], race["event_name"], race["circuit_key"])
        assert race["country"] == CATALOG["hosts"][venue["host"]]["name"], race
    return races, seasons


def luminance(rgb):
    channels = [value / 255 for value in rgb]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def assert_banner_contrast(hero):
    selectors = [".feature-banner__title", ".feature-banner__detail"]
    samples = hero.evaluate("""(hero, selectors) => {
        const frame = hero.getBoundingClientRect();
        return selectors.map(selector => {
            const text = hero.querySelector(selector);
            const range = document.createRange();
            range.selectNodeContents(text);
            const boxes = [...range.getClientRects()].map(r => [r.left - frame.left, r.top - frame.top, r.right - frame.left, r.bottom - frame.top]);
            const colour = getComputedStyle(text).color.match(/\\d+/g).slice(0, 3).map(Number);
            text.style.visibility = 'hidden';
            return {boxes, colour};
        });
    }""", selectors)
    try:
        pixels = Image.open(BytesIO(hero.screenshot())).convert("RGB")
    finally:
        hero.evaluate("(hero, selectors) => selectors.forEach(selector => hero.querySelector(selector).style.removeProperty('visibility'))", selectors)

    for sample, required in zip(samples, (3, 4.5)):
        foreground = luminance(sample["colour"])
        measured = []
        for left, top, right, bottom in sample["boxes"]:
            for y in range(max(0, round(top)), min(pixels.height, round(bottom)), 4):
                for x in range(max(0, round(left)), min(pixels.width, round(right)), 4):
                    background = luminance(pixels.getpixel((x, y)))
                    measured.append((max(foreground, background) + 0.05) / (min(foreground, background) + 0.05))
        assert measured and min(measured) >= required, (required, min(measured, default=0))


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    email = f"session-flag-e2e-{secrets.token_hex(6)}@example.com"
    token = seed_verified_account({"email": email, "password": secrets.token_urlsafe(24)})["access_token"]
    owner = api("GET", "/api/auth/session", token)["user_id"]
    try:
        races, seasons = check_calendar(token)
        sessions = {row["source_session_key"]: row for row in api("GET", "/api/sessions", token)}
        key = "openf1:session:11731"
        sepang = next(row for row in races if row["source_session_key"] == key)
        assert (sepang["circuit_key"], sepang["country"]) == ("12", "Malaysia"), sepang
        sessions[key] = api("POST", "/api/sessions/import", token, {
            "season_year": sepang["season_year"],
            "round_number": sepang["round_number"],
            "session_name": sepang["session_name"],
            "source_session_key": key,
            "import_profile": "core",
        })
        assert (sessions[key]["circuit_key"], sessions[key]["country"]) == ("12", "Malaysia")
        sepang_entries = api("GET", f"/api/sessions/{sessions[key]['id']}/entries", token)
        reference = max(sepang_entries, key=lambda entry: entry["laps_completed"] or 0)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="dark")
            errors = []
            road_requests = []
            page.on("pageerror", lambda event: errors.append(str(event)))
            def record_road(request):
                path = urlsplit(request.url).path
                if path.startswith("/circuit-roads/"):
                    road_requests.append(path)
            page.on("request", record_road)
            page.goto(BASE + "/login")
            page.evaluate("token => localStorage.setItem('auth_token', token)", token)

            def open_session(key, code, layout):
                session = sessions[f"openf1:session:{key}"]
                params = {"mode": "lookback", "layout": f"builtin:{layout}"}
                if key == "11731":
                    road_requests.clear()
                    params["drivers"] = reference["id"]
                page.goto(BASE + f"/sessions/{session['id']}?{urlencode(params)}")
                hero = page.locator(".sessions-workspace__hero")
                expect(hero.get_by_role("heading", name=session["event_name"], exact=True)).to_be_visible()
                expect(hero).to_have_attribute("data-host-flag", code)
                flag = hero.locator(".sessions-workspace__flag")
                expect(flag).to_have_attribute("aria-hidden", "true")
                expect(flag).to_have_attribute("src", f"/host-flags/{code}.webp")
                flag.evaluate("image => image.decode()")
                expect(hero.get_by_role("link", name="Change session")).to_be_visible()
                expect(hero.get_by_role("link", name="Jump to dashboard", exact=False)).to_be_visible()
                return hero

            japan = open_session("11249", "jp", "qualifying-review")
            expect(japan.locator(".sessions-workspace__round")).to_have_text("03")
            assert_banner_contrast(japan)
            japan.screenshot(path=str(ARTIFACTS / "japan-dark.png"))
            page.get_by_role("button", name="Switch to light theme").click()
            expect(page.locator("html")).to_have_attribute("data-theme", "light")
            assert_banner_contrast(japan)
            japan.screenshot(path=str(ARTIFACTS / "japan-light.png"))

            for width in (390, 320):
                page.set_viewport_size({"width": width, "height": 844})
                assert japan.evaluate("""hero => {
                    const flag = hero.querySelector('.sessions-workspace__flag').getBoundingClientRect();
                    const range = document.createRange();
                    range.selectNodeContents(hero.querySelector('.feature-banner__detail'));
                    return hero.getBoundingClientRect().right <= innerWidth && [...range.getClientRects()].every(text =>
                        text.right <= flag.left || text.left >= flag.right || text.top >= flag.bottom || text.bottom <= flag.top);
                }"""), f"Flag must leave room for session details at {width}px"
            page.set_viewport_size({"width": 390, "height": 844})
            assert_banner_contrast(japan)
            japan.screenshot(path=str(ARTIFACTS / "japan-mobile.png"))

            page.set_viewport_size({"width": 1440, "height": 1000})
            page.get_by_role("button", name="Switch to dark theme").click()
            for key, code, layout in [("9987", "it", "session-trends"), ("9693", "au", "session-trends"), ("9943", "gb", "qualifying-review"), ("11731", "my", "session-trends")]:
                other = open_session(key, code, layout)
                assert_banner_contrast(other)
                other.screenshot(path=str(ARTIFACTS / f"{code}-dark.png"))

            sepang_map = page.locator('[data-widget="session-track-map"]')
            expect(sepang_map.get_by_text("Mapped centreline with estimated width.", exact=False)).to_be_visible(timeout=180000)
            assert road_requests == ["/circuit-roads/centrelines/my-1999.csv"], road_requests
            assert sepang_map.locator(".track-map-viewer__track-center").get_attribute("d").endswith(" Z")
            for width in (1440, 390):
                page.set_viewport_size({"width": width, "height": 1000})
                expect(sepang_map.get_by_role("combobox", name="Focus")).to_have_value("pack")
                box = sepang_map.evaluate("""panel => {
                    const rect = selector => panel.querySelector(selector).getBoundingClientRect().toJSON();
                    return {card: rect('.widget-card'), surface: rect('.track-map-viewer__surface'),
                            source: rect('.circuit-map-layers__note')};
                }""")
                card, surface, source = (box[part] for part in ("card", "surface", "source"))
                assert surface["bottom"] <= min(card["bottom"], source["top"]) and surface["right"] <= card["right"] and surface["height"] >= 120, (width, box)
            page.set_viewport_size({"width": 1440, "height": 1000})
            sepang_map.screenshot(path=str(ARTIFACTS / "sepang-lookback.png"))

            sizes = page.evaluate("""async codes => Promise.all(codes.map(async code => {
                const image = new Image();
                image.src = '/host-flags/' + code + '.webp';
                await image.decode();
                return [image.naturalWidth, image.naturalHeight];
            }))""", FLAG_CODES)
            assert all(width == 640 and height > 0 for width, height in sizes), sizes
            assert not errors, errors
            browser.close()
        print(f"Races by season {seasons}, {len({race['circuit_key'] for race in races})} circuits.")
        print(f"Verified real banners in Japan, Italy, Australia, Britain and Malaysia. All {len(FLAG_CODES)} flags decoded.")
        print("Sepang loaded only its own CSV and aligned it to a real lap.")
    finally:
        cleanup = """import sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    row = db.get(UserRecord, sys.argv[1])
    if row and row.email.startswith('session-flag-e2e-'):
        db.delete(row)
        db.commit()
"""
        subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), "-c", cleanup, owner], cwd=ROOT / "backend", check=True)


if __name__ == "__main__":
    main()
