from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import Page, async_playwright


ROOT = Path(__file__).resolve().parents[2]
SHOT_DIR = ROOT / "docs" / "generated" / "ppt-demo" / "screenshots"
LAYOUT_DIR = ROOT / "docs" / "generated" / "ppt-demo" / "layout-screenshots"
TOKEN_PATH = ROOT / "docs" / "generated" / "ppt-demo" / "auth-token.txt"
BASE_URL = "http://127.0.0.1:5173"
SESSION_ID = "8f6959c6-fe38-4643-9213-8536113116b0"
VER_ENTRY_ID = "c9decd5d-10a9-4e8f-87db-b71c930ef54a"


def workspace_path(mode: str, layout: str, lap: str | int = "all") -> str:
    params = urlencode({"mode": mode, "layout": layout, "lap": str(lap)})
    return f"/sessions/{SESSION_ID}?{params}"


async def seed_auth(page: Page, token: str) -> None:
    await page.add_init_script(
        f"""
          window.localStorage.setItem("auth_token", {json.dumps(token)});
          window.localStorage.removeItem("pitwall.active-session-workspace");
        """
    )


async def prepare_workspace(page: Page, path: str) -> None:
    await page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded")
    await page.wait_for_selector("text=20 loaded", timeout=30_000)
    await page.wait_for_load_state("networkidle", timeout=20_000)
    await page.add_style_tag(
        content="""
          * { scroll-behavior: auto !important; }
          header { display: none !important; visibility: hidden !important; }
          .vite-error-overlay { display: none !important; }
        """
    )


async def click_driver(page: Page, label: str) -> None:
    await page.locator(".sessions-driver-chip").filter(has_text=label).first.click(timeout=12_000)
    await page.wait_for_timeout(500)


async def capture_layout_selector(page: Page) -> dict[str, object]:
    await prepare_workspace(page, workspace_path("lookback", "builtin:session-trends"))
    await click_driver(page, "VER")
    await click_driver(page, "LEC")
    await click_driver(page, "HAM")
    await page.wait_for_selector("text=3 of 20 drivers selected", timeout=20_000)

    locator = page.locator(".sessions-control-panel--layouts").first
    await locator.scroll_into_view_if_needed(timeout=20_000)
    await page.wait_for_timeout(1_000)
    path = SHOT_DIR / "08_layout_selector.png"
    await locator.screenshot(path=path, animations="disabled")
    return {"name": "layout_selector", "path": str(path), "box": await locator.bounding_box()}


async def set_replay_to_mid_race(page: Page) -> None:
    slider = page.locator(".sessions-replay-timeline input[type='range']").first
    await slider.wait_for(timeout=25_000)
    await slider.evaluate(
        """
        (el) => {
          const min = Number(el.min || 0);
          const max = Number(el.max || min + 1);
          const value = Math.round(min + ((max - min) * 0.55));
          el.value = String(value);
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
        }
        """
    )
    await page.wait_for_timeout(800)


async def configure_track_map(page: Page) -> None:
    await page.locator(".track-map-focus-select select").first.wait_for(timeout=25_000)
    await page.locator(".track-map-focus-select select").first.select_option(value=VER_ENTRY_ID)
    zoom_in = page.get_by_role("button", name="Zoom in").first
    await zoom_in.click(timeout=10_000)
    await zoom_in.click(timeout=10_000)
    await page.wait_for_timeout(500)


async def capture_ver_replay_focus(page: Page) -> dict[str, object]:
    await prepare_workspace(page, workspace_path("simulation", "builtin:replay-focus"))
    await click_driver(page, "VER")
    await page.wait_for_selector("text=1 of 20 drivers selected", timeout=20_000)
    await set_replay_to_mid_race(page)
    await page.get_by_role("button", name="5x").click(timeout=10_000)
    await configure_track_map(page)
    await page.get_by_role("button", name="Start").click(timeout=10_000)
    await page.wait_for_timeout(2_000)

    locator = page.locator(".dashboard-section .widget-card").first
    await locator.scroll_into_view_if_needed(timeout=20_000)
    await page.wait_for_timeout(800)
    path = LAYOUT_DIR / "06_replay_ver_focus_midrace.png"
    await locator.screenshot(path=path, animations="disabled")
    return {"name": "ver_replay_focus_midrace", "path": str(path), "box": await locator.bounding_box()}


async def main() -> None:
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    LAYOUT_DIR.mkdir(parents=True, exist_ok=True)
    token = TOKEN_PATH.read_text(encoding="utf-8-sig").strip()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1800, "height": 1400},
            device_scale_factor=1,
            color_scheme="dark",
            locale="hu-HU",
        )
        page = await context.new_page()
        await seed_auth(page, token)

        results = [
            await capture_layout_selector(page),
            await capture_ver_replay_focus(page),
        ]

        await browser.close()

    summary_path = LAYOUT_DIR / "ppt-update-screenshots.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    for result in results:
        print(f"{result['name']}: {result['path']}")


if __name__ == "__main__":
    asyncio.run(main())
