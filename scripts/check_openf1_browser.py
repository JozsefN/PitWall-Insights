"""Current OpenF1 workflow with a verified test account and one fixture calendar case."""
from local_test_accounts import seed_verified_account
import json
from pathlib import Path
import re
import secrets
import subprocess
from time import monotonic
from urllib.request import Request, urlopen
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs/testing/openf1-browser"
BASE = "http://127.0.0.1:4173"


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    users, checks, errors, calls = [], [], [], []
    def api(path, token):
        with urlopen(Request("http://127.0.0.1:8000" + path, headers={"Authorization":"Bearer " + token}), timeout=30) as response:
            return json.load(response)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width":1440,"height":1000})
            page.set_default_timeout(15_000)
            page.on("pageerror",lambda error: errors.append(str(error)))
            page.on("request",lambda request: calls.append(request.url))
            page.goto(BASE + "/signup")
            expect(page.get_by_label("F1 account email")).to_have_count(0)
            expect(page.get_by_role("checkbox")).to_have_count(0)
            credentials = {"email": "openf1-e2e-" + secrets.token_hex(6) + "@example.com", "password": secrets.token_urlsafe(20)}
            fixture = seed_verified_account(credentials)
            users.append(fixture["user_id"])
            page.goto(BASE + "/login")
            page.get_by_label("Email",exact=True).fill(credentials["email"])
            page.get_by_label("Password",exact=True).fill(credentials["password"])
            page.locator(".account-access__form").get_by_role("button",name="Sign in",exact=True).click()
            page.wait_for_url(BASE + "/")
            token = page.evaluate("localStorage.getItem('auth_token')")
            checks.append("verified_local_login_works_without_an_f1_account_or_extension")
            page.get_by_role("link",name="Open profile",exact=True).click()
            page.get_by_label("Display name").fill("OpenF1 Browser Driver")
            page.get_by_label("Nickname").fill("Apex")
            page.get_by_role("button",name="Save details",exact=True).click()
            expect(page.get_by_role("status")).to_have_text("Details saved")
            page.reload()
            expect(page.get_by_label("Nickname")).to_have_value("Apex")
            expect(page.get_by_role("button",name="Connect F1 account",exact=True)).to_have_count(0)
            checks.append("profile_persists_without_external_connection_controls")
            page.get_by_role("button",name="Data availability",exact=True).click()
            for feature in ("Brake trace","Track map and historical replay","Historical strategy calculations"):
                row=page.get_by_role("row").filter(has=page.get_by_role("rowheader",name=feature,exact=False))
                expect(row.get_by_label("Supported",exact=True)).to_have_count(1)
            expect(page.get_by_role("columnheader")).to_have_count(2)
            page.screenshot(path=str(ARTIFACTS / "availability.png"),full_page=True)
            page.set_viewport_size({"width":390,"height":844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            checks.append("one_source_availability_and_mobile_layout")
            page.set_viewport_size({"width":1440,"height":1000})
            catalog=[{"source":"openf1","source_event_key":"fixture:meeting","source_session_key":key,"season_year":2025,"round_number":1,"event_name":"Australian Grand Prix","location":"Melbourne","session_name":name,"scheduled_start_utc":"2025-03-16T04:00:00Z","available_for_import":available,"unavailable_reason":None if available else "Available as history 30 minutes after the session ends."} for key,name,available in (("fixture:future","Qualifying",False),("openf1:session:9693","Race",True))]
            page.route("**/api/sessions/catalog?*",lambda route:route.fulfill(status=200,json=catalog))
            page.goto(BASE + "/sessions?view=explorer&season=2025")
            expect(page.get_by_label("Data source",exact=True)).to_have_count(0)
            expect(page.get_by_role("button",name="Load session",exact=True)).to_be_disabled()
            expect(page.get_by_text("Available as history 30 minutes after the session ends.",exact=True)).to_be_visible()
            checks.append("unavailable_session_explained_without_provider_selection")
            page.locator(".sessions-catalog").get_by_role("button",name=re.compile(r"^Race\s")).click()
            page.get_by_role("button",name="Load session",exact=True).click()
            page.wait_for_url(re.compile(r"/sessions/[a-f0-9-]+\?"),timeout=90_000)
            sid=page.url.split("/sessions/",1)[1].split("?",1)[0]
            entries=api(f"/api/sessions/{sid}/entries",token)
            entries=[entry for entry in entries if entry["car_number"] in ("1","4","16")]
            assert len(entries)==3
            checks.append("real_openf1_core_import_opens_workspace")
            started=monotonic()
            drivers=",".join(entry["id"] for entry in entries)
            timeline, car_samples, position_samples = [], [], []
            ready_to_release = (
                ("**/api/sessions/*/replay-timeline", timeline),
                ("**/telemetry/car?*", car_samples),
                ("**/telemetry/position?*", position_samples),
            )

            def hold_in(queue):
                def hold(route):
                    queue.append(route)
                return hold

            for pattern, requests in ready_to_release:
                page.route(pattern, hold_in(requests))
            page.goto(BASE + f"/sessions/{sid}?mode=simulation&layout=builtin:replay-focus&drivers={drivers}&lap=all")
            start = page.get_by_role("button", name="Start", exact=True)
            status = page.locator("#replay-start-status")
            replay_panels = page.locator(".responsive-widget")
            expect(replay_panels).to_have_count(2)
            def panel_heights():
                return replay_panels.evaluate_all("nodes => nodes.map(node => node.offsetHeight)")

            configured_heights = panel_heights()
            assert configured_heights == [360, 220]
            for (pattern, requests), message in zip(ready_to_release, (
                "Loading the replay timeline",
                "Loading car telemetry samples",
                "Loading position telemetry samples",
            )):
                expect(start).to_be_disabled()
                expect(status).to_contain_text(message, timeout=180_000)
                assert panel_heights() == configured_heights
                start.evaluate("node => node.click()")
                expect(page.get_by_role("button", name="Pause", exact=True)).to_have_count(0)
                assert requests, message
                for request in requests:
                    request.continue_()
                page.unroute(pattern)
            expect(start).to_be_enabled(timeout=180_000)
            expect(status).to_have_text("")
            checks.append("start_waits_for_timeline_and_required_car_and_position_samples")
            slider=page.locator(".sessions-replay-timeline input[type=range]")
            slider.evaluate("(node)=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(node,'10000000');node.dispatchEvent(new Event('input',{bubbles:true}));}")
            expect(page.locator(".track-map-viewer__driver-dot")).to_have_count(3,timeout=180_000)
            expect(page.locator(".replay-driver-card")).to_have_count(3,timeout=30_000)
            assert panel_heights() == configured_heights
            page.set_viewport_size({"width": 390, "height": 844})
            assert panel_heights() == configured_heights
            page.set_viewport_size({"width": 1440, "height": 1000})
            startup=monotonic()-started
            assert startup < 180, startup
            before=float(slider.input_value())
            page.get_by_role("button",name="Start",exact=True).click()
            page.wait_for_function("start => Number(document.querySelector('.sessions-replay-timeline input').value)>start+500",arg=before)
            page.get_by_role("button",name="Pause",exact=True).click()
            page.screenshot(path=str(ARTIFACTS / "replay.png"),full_page=True)
            checks.append("real_three_driver_replay_loads_and_advances_under_180_seconds")
            start.click()
            page.get_by_role("button", name="Clear", exact=True).click()
            expect(start).to_be_disabled()
            expect(status).to_contain_text("Choose at least one driver")
            expect(page.get_by_role("button", name="Pause", exact=True)).to_have_count(0)
            assert panel_heights() == configured_heights
            checks.append("changing_drivers_pauses_and_missing_selection_explains_start_lock")
            checks.append("factory_replay_panels_keep_their_height_during_load_playback_and_driver_changes")
            page.route("**/api/sessions/*/replay-timeline", lambda route: route.fulfill(
                status=503,
                headers={"Access-Control-Allow-Origin": BASE},
                json={"detail": "Test timeline unavailable"},
            ))
            page.reload()
            expect(status).to_contain_text("The replay timeline could not be loaded")
            expect(start).to_be_disabled()
            checks.append("timeline_failure_keeps_start_locked_with_retry_guidance")
            assert not any("/connections/f1" in url for url in calls)
            assert not errors, errors
            browser.close()
    finally:
        cleanup="""import json,sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    for key in json.load(sys.stdin):
        user=db.get(UserRecord,key)
        if user and user.email.startswith('openf1-e2e-'): db.delete(user)
    db.commit()
"""
        subprocess.run([str(ROOT/"backend/.venv/Scripts/python.exe"),"-c",cleanup],input=json.dumps(users),text=True,cwd=ROOT/"backend",check=True)
    report={"checks":checks,"count":len(checks),"browser_errors":errors,"replay_startup_seconds":round(startup,3),"real_openf1_import_and_replay":True,"future_calendar_case_simulated":True,"external_account_requests":0,"test_accounts_removed":True}
    (ARTIFACTS/"results.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__": main()
