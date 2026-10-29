from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import Browser, Page, async_playwright


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "docs" / "generated" / "ppt-demo" / "screenshots"
TOKEN_PATH = ROOT / "docs" / "generated" / "ppt-demo" / "auth-token.txt"
BASE_URL = "http://127.0.0.1:5173"

SESSION_ID = "8f6959c6-fe38-4643-9213-8536113116b0"
DRIVERS = {
    "VER": "c9decd5d-10a9-4e8f-87db-b71c930ef54a",
    "LEC": "2a477eca-0c7d-4d03-8d67-6b995b2f7cee",
    "HAM": "323de5c2-0b31-425c-8817-fca23e820655",
    "NOR": "5159d406-03f9-4115-9aed-b6a64cc32ab1",
}


def workspace_url(mode: str, layout: str, drivers: list[str], lap: str | int = "all") -> str:
    params = urlencode(
        {
            "mode": mode,
            "layout": layout,
            "drivers": ",".join(DRIVERS[key] for key in drivers),
            "lap": str(lap),
        }
    )
    return f"/sessions/{SESSION_ID}?{params}"


SHOTS = [
    {
        "name": "01_logged_out_sessions_gate",
        "path": "/sessions",
        "auth": False,
        "wait_for": "text=Member feature",
    },
    {
        "name": "02_signup",
        "path": "/signup",
        "auth": False,
        "wait_for": "text=Create account",
    },
    {
        "name": "03_login",
        "path": "/login",
        "auth": False,
        "wait_for": "text=Sign in",
    },
    {
        "name": "04_home_authenticated",
        "path": "/",
        "auth": True,
        "wait_for": "text=Session Explorer",
    },
    {
        "name": "05_system_health",
        "path": "/system/health",
        "auth": True,
        "wait_for": "text=System",
    },
    {
        "name": "06_session_explorer",
        "path": "/sessions?view=explorer",
        "auth": True,
        "wait_for": "text=Session Explorer",
        "clear_resume": True,
    },
    {
        "name": "07_workspace_driver_selection",
        "path": workspace_url("lookback", "builtin:session-trends", []),
        "auth": True,
        "wait_for": "text=20 loaded",
        "click_exact": ["VER", "LEC", "HAM"],
        "post_wait_for": "text=3 of 20 drivers selected",
    },
    {
        "name": "08_lookback_session_trends",
        "path": workspace_url("lookback", "builtin:session-trends", []),
        "auth": True,
        "wait_for": "text=20 loaded",
        "click_exact": ["VER", "LEC", "HAM"],
        "post_wait_for": "text=3 of 20 drivers selected",
        "scroll_to": "Session Overview",
    },
    {
        "name": "09_compare_lap",
        "path": workspace_url("lookback", "builtin:compare-lap", []),
        "auth": True,
        "wait_for": "text=20 loaded",
        "click_exact": ["VER", "LEC"],
        "post_wait_for": "text=2 of 20 drivers selected",
        "click_after_wait": ["Lap 10"],
        "scroll_to": "Lap Traces",
    },
    {
        "name": "10_stint_strategy",
        "path": workspace_url("lookback", "builtin:stint-strategy", []),
        "auth": True,
        "wait_for": "text=20 loaded",
        "click_exact": ["VER", "LEC", "HAM"],
        "post_wait_for": "text=3 of 20 drivers selected",
        "scroll_to": "Stint Analysis",
    },
    {
        "name": "11_replay_command",
        "path": workspace_url("simulation", "builtin:replay-command", []),
        "auth": True,
        "wait_for": "text=20 loaded",
        "click_exact": ["VER", "LEC", "HAM"],
        "post_wait_for": "text=3 of 20 drivers selected",
        "scroll_to": "Replay Surface",
    },
]


async def prepare_page(page: Page, token: str, authenticated: bool, clear_resume: bool = False) -> None:
    if authenticated:
        token_json = json.dumps(token)
        clear_resume_json = json.dumps(clear_resume)
        await page.add_init_script(
            f"""
                const token = {token_json};
                const clearResume = {clear_resume_json};
                window.localStorage.setItem("auth_token", token);
                if (clearResume) {{
                    window.localStorage.removeItem("pitwall.active-session-workspace");
                }}
            """
        )
    else:
        await page.add_init_script(
            """
                window.localStorage.removeItem("auth_token");
                window.localStorage.removeItem("pitwall.active-session-workspace");
            """
        )


async def capture(browser: Browser, shot: dict[str, object], token: str) -> dict[str, str]:
    context = await browser.new_context(
        viewport={"width": 1600, "height": 900},
        device_scale_factor=1,
        color_scheme="dark",
        locale="hu-HU",
    )
    page = await context.new_page()
    await prepare_page(
        page,
        token,
        bool(shot.get("auth")),
        bool(shot.get("clear_resume")),
    )
    await page.goto(f"{BASE_URL}{shot['path']}", wait_until="domcontentloaded")
    if wait_for := shot.get("wait_for"):
        try:
            await page.wait_for_selector(str(wait_for), timeout=15_000)
        except Exception:
            await page.wait_for_timeout(2_000)
    for label in shot.get("click_exact", []):
        await page.get_by_text(str(label), exact=True).first.click(timeout=10_000)
        await page.wait_for_timeout(300)
    if post_wait_for := shot.get("post_wait_for"):
        await page.wait_for_selector(str(post_wait_for), timeout=20_000)
    for label in shot.get("click_after_wait", []):
        await page.get_by_text(str(label), exact=True).first.click(timeout=10_000)
        await page.wait_for_timeout(500)
    await page.wait_for_load_state("networkidle", timeout=15_000)
    await page.wait_for_timeout(2_500)
    if scroll_to := shot.get("scroll_to"):
        await page.get_by_text(str(scroll_to), exact=True).first.scroll_into_view_if_needed(timeout=20_000)
        await page.wait_for_timeout(2_500)
    await page.add_style_tag(
        content="""
            * { scroll-behavior: auto !important; }
            body { overflow: hidden !important; }
            .vite-error-overlay { display: none !important; }
        """
    )
    path = OUTPUT_DIR / f"{shot['name']}.png"
    await page.screenshot(path=path, full_page=False)
    title = await page.title()
    url = page.url
    await context.close()
    return {"name": str(shot["name"]), "path": str(path), "title": title, "url": url}


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    token = TOKEN_PATH.read_text(encoding="utf-8-sig").strip()
    if not token:
        raise RuntimeError(f"Missing auth token in {TOKEN_PATH}")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        results = []
        for shot in SHOTS:
            results.append(await capture(browser, shot, token))
        await browser.close()

    summary_path = OUTPUT_DIR / "screenshots.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    for result in results:
        print(f"{result['name']}: {result['path']}")


if __name__ == "__main__":
    asyncio.run(main())
