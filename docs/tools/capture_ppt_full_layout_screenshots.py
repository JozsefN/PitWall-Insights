from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import Page, async_playwright


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "docs" / "generated" / "ppt-demo" / "layout-screenshots"
TOKEN_PATH = ROOT / "docs" / "generated" / "ppt-demo" / "auth-token.txt"
BASE_URL = "http://127.0.0.1:5173"
SESSION_ID = "8f6959c6-fe38-4643-9213-8536113116b0"


def workspace_path(mode: str, layout: str, lap: str | int = "all") -> str:
    params = urlencode({"mode": mode, "layout": layout, "lap": str(lap)})
    return f"/sessions/{SESSION_ID}?{params}"


FULL_LAYOUT_SHOTS = [
    {
        "name": "01_session_trends_full",
        "path": workspace_path("lookback", "builtin:session-trends"),
        "drivers": ["VER", "LEC", "HAM"],
        "ready_text": "3 of 20 drivers selected",
        "target": ".dashboard-section",
        "index": 0,
    },
    {
        "name": "02_compare_lap_full",
        "path": workspace_path("lookback", "builtin:compare-lap"),
        "drivers": ["VER", "LEC"],
        "click_after_drivers": ["Lap 10"],
        "ready_text": "2 of 20 drivers selected",
        "target": ".dashboard-section",
        "index": 0,
    },
    {
        "name": "03_stint_strategy_full",
        "path": workspace_path("lookback", "builtin:stint-strategy"),
        "drivers": ["VER", "LEC", "HAM"],
        "ready_text": "3 of 20 drivers selected",
        "target": ".dashboard-section",
        "index": 0,
    },
    {
        "name": "04_replay_command_full",
        "path": workspace_path("simulation", "builtin:replay-command"),
        "drivers": ["VER", "LEC", "HAM"],
        "ready_text": "3 of 20 drivers selected",
        "target": ".dashboard-section",
        "index": 0,
    },
    {
        "name": "05_replay_focus_full",
        "path": workspace_path("simulation", "builtin:replay-focus"),
        "drivers": ["VER", "LEC", "HAM"],
        "ready_text": "3 of 20 drivers selected",
        "target": ".dashboard-section .widget-card",
        "index": 0,
    },
]


async def seed_auth(page: Page, token: str) -> None:
    await page.add_init_script(
        f"""
          window.localStorage.setItem("auth_token", {json.dumps(token)});
          window.localStorage.removeItem("pitwall.active-session-workspace");
        """
    )


async def click_driver(page: Page, label: str) -> None:
    await page.get_by_text(label, exact=True).first.click(timeout=10_000)
    await page.wait_for_timeout(300)


async def capture_full_layout(page: Page, shot: dict[str, object]) -> dict[str, object]:
    await page.goto(f"{BASE_URL}{shot['path']}", wait_until="domcontentloaded")
    await page.wait_for_selector("text=20 loaded", timeout=25_000)

    for driver in shot.get("drivers", []):
        await click_driver(page, str(driver))

    if ready_text := shot.get("ready_text"):
        await page.wait_for_selector(f"text={ready_text}", timeout=25_000)

    for label in shot.get("click_after_drivers", []):
        await page.get_by_text(str(label), exact=True).first.click(timeout=10_000)
        await page.wait_for_timeout(500)

    await page.wait_for_load_state("networkidle", timeout=20_000)
    await page.wait_for_timeout(3_000)
    await page.add_style_tag(
        content="""
          * { scroll-behavior: auto !important; }
          header { display: none !important; visibility: hidden !important; }
          .vite-error-overlay { display: none !important; }
        """
    )

    locator = page.locator(str(shot["target"])).nth(int(shot.get("index", 0)))
    await locator.scroll_into_view_if_needed(timeout=20_000)
    await page.wait_for_timeout(1_000)
    box = await locator.bounding_box()
    path = OUTPUT_DIR / f"{shot['name']}.png"
    await locator.screenshot(path=path, animations="disabled")

    return {
        "name": shot["name"],
        "path": str(path),
        "url": page.url,
        "box": box,
    }


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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

        results = []
        for shot in FULL_LAYOUT_SHOTS:
            results.append(await capture_full_layout(page, shot))

        await browser.close()

    summary_path = OUTPUT_DIR / "layout-screenshots.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    for result in results:
        print(f"{result['name']}: {result['path']}")


if __name__ == "__main__":
    asyncio.run(main())
