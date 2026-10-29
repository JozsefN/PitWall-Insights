from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode

import imageio_ffmpeg
from playwright.async_api import Page, async_playwright


ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = ROOT / "docs" / "generated" / "ppt-demo" / "videos"
RAW_DIR = VIDEO_DIR / "raw"
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


async def prepare_video_stage(page: Page) -> None:
    await page.add_style_tag(
        content="""
          * { scroll-behavior: auto !important; }
          html, body, #root {
            width: 100vw !important;
            height: 100vh !important;
            margin: 0 !important;
            overflow: hidden !important;
            background: #050506 !important;
          }
          header,
          nav,
          .app-shell__header,
          .sessions-workspace__hero,
          .sessions-workspace__controls,
          .sessions-workspace__stage-header,
          .vite-error-overlay {
            display: none !important;
            visibility: hidden !important;
          }
          main,
          .page-container,
          .sessions-workspace,
          .sessions-workspace__body,
          .sessions-workspace__stage,
          .sessions-workspace__stage-body,
          .dashboard-section {
            position: static !important;
            width: 100vw !important;
            max-width: none !important;
            height: 100vh !important;
            min-height: 100vh !important;
            margin: 0 !important;
            padding: 0 !important;
            display: block !important;
            background: #050506 !important;
          }
          .dashboard-section .layout-widget:not(:has(.track-map-viewer)),
          .dashboard-section .widget-card:not(:has(.track-map-viewer)) {
            display: none !important;
            visibility: hidden !important;
            pointer-events: none !important;
          }
          .dashboard-section .layout-widget:has(.track-map-viewer) {
            position: fixed !important;
            inset: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            margin: 0 !important;
            padding: 0 !important;
            z-index: 9999 !important;
          }
          .dashboard-section .widget-card:has(.track-map-viewer) {
            position: fixed !important;
            inset: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            margin: 0 !important;
            border-radius: 0 !important;
            border: 0 !important;
            box-shadow: none !important;
            z-index: 10000 !important;
          }
          .track-map-viewer {
            height: 100vh !important;
            min-height: 100vh !important;
            padding: 18px !important;
            box-sizing: border-box !important;
          }
          .track-map-viewer__surface {
            flex: 1 1 auto !important;
            min-height: 0 !important;
          }
        """
    )


async def click_driver(page: Page, label: str) -> None:
    await page.locator(".sessions-driver-chip").filter(has_text=label).first.click(timeout=12_000)
    await page.wait_for_timeout(500)


async def set_replay_time(page: Page, ratio: float) -> None:
    slider = page.locator(".sessions-replay-timeline input[type='range']").first
    await slider.wait_for(timeout=25_000)
    await slider.evaluate(
        """
        (el, ratio) => {
          const min = Number(el.min || 0);
          const max = Number(el.max || min + 1);
          const value = Math.round(min + ((max - min) * ratio));
          el.value = String(value);
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
        }
        """,
        ratio,
    )
    await page.wait_for_timeout(700)


async def record_replay_video(page: Page, record_started_at: float) -> float:
    await page.goto(
        f"{BASE_URL}{workspace_path('simulation', 'builtin:replay-focus')}",
        wait_until="domcontentloaded",
    )
    await page.wait_for_selector("text=20 loaded", timeout=30_000)
    await click_driver(page, "VER")
    await page.wait_for_selector("text=1 of 20 drivers selected", timeout=20_000)
    await set_replay_time(page, 0.55)
    await page.get_by_role("button", name="5x").click(timeout=10_000)
    await page.wait_for_selector(".track-map-focus-select select", timeout=25_000)
    await page.get_by_role("button", name="Start").click(timeout=10_000)
    await page.wait_for_timeout(500)
    await prepare_video_stage(page)
    await page.locator(".dashboard-section .widget-card").first.scroll_into_view_if_needed(timeout=20_000)
    sequence_started_at = time.monotonic()
    await page.wait_for_timeout(1_200)

    await page.locator(".track-map-focus-select select").first.select_option(value=VER_ENTRY_ID)
    await page.wait_for_timeout(1_200)

    zoom_in = page.get_by_role("button", name="Zoom in").first
    await zoom_in.click(timeout=10_000)
    await page.wait_for_timeout(900)
    await zoom_in.click(timeout=10_000)
    await page.wait_for_timeout(1_200)

    await page.get_by_role("button", name="Show racing lines").click(timeout=10_000)
    await page.wait_for_timeout(1_000)
    await page.get_by_role("button", name="Show racing lines").click(timeout=10_000)
    await page.wait_for_timeout(900)

    await page.get_by_role("button", name="Show previous lap ghost").click(timeout=10_000)
    await page.wait_for_timeout(900)
    await page.get_by_role("button", name="Show previous lap ghost").click(timeout=10_000)
    await page.wait_for_timeout(1_600)
    return sequence_started_at - record_started_at


def convert_to_mp4(source_webm: Path, target_mp4: Path, trim_start_seconds: float, duration_seconds: float) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source_webm),
        "-ss",
        f"{max(trim_start_seconds, 0):.2f}",
        "-t",
        f"{duration_seconds:.2f}",
        "-vf",
        "fps=30,scale=1280:720:flags=lanczos,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "22",
        "-movflags",
        "+faststart",
        str(target_mp4),
    ]
    subprocess.run(command, check=True)


async def main() -> None:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_run_dir = RAW_DIR / f"run-{int(time.time())}"
    raw_run_dir.mkdir(parents=True, exist_ok=True)

    token = TOKEN_PATH.read_text(encoding="utf-8-sig").strip()
    target_mp4 = VIDEO_DIR / "replay_ver_focus_controls.mp4"

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=raw_run_dir,
            record_video_size={"width": 1280, "height": 720},
            color_scheme="dark",
            locale="hu-HU",
        )
        page = await context.new_page()
        record_started_at = time.monotonic()
        await seed_auth(page, token)
        trim_start_seconds = await record_replay_video(page, record_started_at)
        video = page.video
        await page.close()
        await context.close()
        await browser.close()

    raw_candidates = sorted(raw_run_dir.glob("*.webm"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not raw_candidates:
        raise RuntimeError("Playwright did not produce a WebM recording.")

    raw_webm = raw_candidates[0]
    stable_webm = VIDEO_DIR / "replay_ver_focus_controls.webm"
    shutil.copy2(raw_webm, stable_webm)
    convert_to_mp4(stable_webm, target_mp4, trim_start_seconds - 0.3, 10.5)

    summary = {
        "webm": str(stable_webm),
        "mp4": str(target_mp4),
        "created_at": int(time.time()),
        "video_object_present": video is not None,
        "trim_start_seconds": round(trim_start_seconds - 0.3, 2),
        "duration_seconds": 10.5,
    }
    (VIDEO_DIR / "replay-video.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"webm: {stable_webm}")
    print(f"mp4: {target_mp4}")


if __name__ == "__main__":
    asyncio.run(main())
