"""Real local signup/profile persistence; F1 HTTP responses are explicitly simulated."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import secrets
import subprocess
from urllib.request import Request, urlopen
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs/testing/profile-browser"


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    users, checks, errors = [], [], []
    fake_connection = None
    expires = (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
    def api(path, token):
        with urlopen(Request("http://127.0.0.1:8000"+path, headers={"Authorization":"Bearer "+token}),timeout=20) as response:
            return json.load(response)
    try:
        with sync_playwright() as browser_api:
            browser = browser_api.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width":1440,"height":1100})
            page.set_default_timeout(12_000)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("http://127.0.0.1:4173/signup")
            account="profile-e2e-"+secrets.token_hex(6)+"@example.com"
            page.get_by_label("Email",exact=True).fill(account)
            page.get_by_label("Password",exact=True).fill(secrets.token_urlsafe(20))
            expect(page.get_by_label("F1 account email")).to_have_count(0)
            page.get_by_role("button",name="Sign up",exact=True).click()
            page.wait_for_url("http://127.0.0.1:4173/")
            token=page.evaluate("localStorage.getItem('auth_token')")
            users.append(api("/api/auth/session",token)["user_id"])
            checks.append("signup_without_external_account")
            page.get_by_role("link",name="Open profile",exact=True).click()
            page.wait_for_url("**/profile")
            page.get_by_label("Display name").fill("Browser Driver")
            page.get_by_label("Nickname").fill("Apex")
            page.get_by_text("Contact information",exact=False).click()
            page.get_by_label("Phone number").fill("+36 30 123 4567")
            page.get_by_role("button",name="Save details").click()
            expect(page.get_by_role("status")).to_have_text("Details saved")
            assert api("/api/profile",token)["nickname"]=="Apex"
            page.reload()
            expect(page.get_by_label("Display name")).to_have_value("Browser Driver")
            checks.append("profile_persists_in_real_database_after_reload")
            page.screenshot(path=str(ARTIFACTS/"profile-desktop.png"),full_page=True)
            page.get_by_role("button",name="Data availability",exact=True).click()
            for feature in ("Brake trace", "Track map and historical replay", "Historical strategy calculations"):
                row=page.get_by_role("row").filter(has=page.get_by_role("rowheader",name=feature,exact=False))
                expect(row.get_by_label("Supported",exact=True)).to_have_count(2)
            row=page.get_by_role("row").filter(has=page.get_by_role("rowheader",name="Live race viewer in PitWall",exact=False))
            expect(row.get_by_label("Unavailable",exact=True)).to_have_count(2)
            checks.append("data_availability_shows_free_brake_replay_strategy_and_unavailable_live_with_checks")
            page.screenshot(path=str(ARTIFACTS/"data-availability.png"),full_page=True)
            page.set_viewport_size({"width":390,"height":844})
            expect(page.get_by_role("link",name="Open profile",exact=True)).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.get_by_role("button",name="Profile & connections",exact=True).click()
            expect(page.get_by_label("Display name")).to_have_value("Browser Driver")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(ARTIFACTS/"profile-mobile.png"),full_page=True)
            checks.append("mobile_profile_and_comparison_do_not_overflow_page")
            page.set_viewport_size({"width":1440,"height":1100})
            page.get_by_role("button",name="Saved login",exact=True).click()
            def fail_connection(route):
                route.fulfill(status=400,json={"detail":{"code":"f1_sign_in_changed","message":"F1 verification fixture: try browser sign-in","action_url":"/profile?connect=f1"}})
            page.route("**/api/profile/connections/f1",fail_connection)
            page.get_by_label("F1 account email",exact=True).fill("f1-fixture@example.com")
            page.get_by_label("F1 account password",exact=True).fill("fixture-f1-password")
            page.get_by_label("Keep my connection using encrypted credentials",exact=False).check()
            page.get_by_role("button",name="Connect F1 account",exact=True).click()
            expect(page.get_by_role("alert")).to_contain_text("F1 verification fixture")
            assert "fixture-f1-password" not in page.evaluate("JSON.stringify(localStorage)")
            checks.append("failed_f1_connection_preserves_free_account_and_no_provider_secret_in_local_storage")
            page.unroute("**/api/profile/connections/f1",fail_connection)
            def simulate_profile(route):
                response=route.fetch()
                body=response.json()
                if fake_connection is not None:
                    body["f1_connection"]=fake_connection
                route.fulfill(response=response,json=body)
            page.route("**/api/profile",simulate_profile)
            def simulate_connection(route):
                nonlocal fake_connection
                if route.request.method=="DELETE":
                    fake_connection={"status":"not_connected","connected":False,"persistent":False,"expires_at":None}
                else:
                    fake_connection={"status":"connected","connected":True,"persistent":True,"expires_at":expires}
                route.fulfill(status=200,json=fake_connection)
            page.route("**/api/profile/connections/f1",simulate_connection)
            page.route("**/api/profile/connections/f1/verify",lambda route:route.fulfill(status=200,json=fake_connection))
            page.get_by_label("F1 account password",exact=True).fill("fixture-f1-password")
            page.get_by_role("button",name="Connect F1 account",exact=True).click()
            expect(page.get_by_text("Connected",exact=True)).to_be_visible()
            page.get_by_role("button",name="Check connection",exact=True).click()
            expect(page.get_by_role("status")).to_contain_text("Connection is ready")
            page.get_by_role("button",name="Disconnect",exact=True).click()
            page.get_by_role("button",name="Keep connection",exact=True).click()
            expect(page.get_by_text("Connected",exact=True)).to_be_visible()
            page.get_by_role("button",name="Disconnect",exact=True).click()
            page.get_by_role("button",name="Disconnect F1 account",exact=True).click()
            expect(page.get_by_label("F1 account email",exact=True)).to_be_visible()
            checks.append("simulated_f1_connect_verify_and_confirmed_disconnect")
            page.get_by_role("button",name="Browser sign-in",exact=True).click()
            page.get_by_label("I approve the Companion handoff",exact=False).check()
            with page.expect_popup() as popup_info:
                page.get_by_role("button",name="Sign in on Formula1.com",exact=True).click()
            popup=popup_info.value
            expect(page.get_by_text("Waiting for Formula 1 sign-in",exact=False)).to_be_visible()
            expect(page.get_by_role("link",name="Open Formula 1 sign-in again",exact=False)).to_have_attribute("href",__import__('re').compile(r"https://f1login\.fastf1\.dev\?port=\d+"))
            page.get_by_role("button",name="Cancel browser sign-in",exact=True).click()
            expect(page.get_by_role("button",name="Sign in on Formula1.com",exact=True)).to_be_visible()
            popup.close()
            checks.append("real_local_browser_handoff_start_wait_and_cancel_without_sending_credentials")

            # Provider success is simulated; account/profile persistence above uses the real API.
            def browser_start(route):
                route.fulfill(status=200,json={"id":"browser-fixture","url":"https://f1login.fastf1.dev?port=12345","expires_at":expires})
            page.route("**/api/profile/connections/f1/browser",browser_start)
            page.route("**/api/profile/connections/f1/browser/browser-fixture",lambda route:route.fulfill(status=200,json={"state":"ready","account_hint":"f1-fixture@example.com","error":None}))
            def browser_confirm(route):
                nonlocal fake_connection
                fake_connection={"status":"connected","connected":True,"persistent":True,"expires_at":expires,"auth_method":"browser"}
                route.fulfill(status=200,json=fake_connection)
            page.route("**/api/profile/connections/f1/browser/browser-fixture/confirm",browser_confirm)
            with page.expect_popup() as popup_info:
                page.get_by_role("button",name="Sign in on Formula1.com",exact=True).click()
            popup=popup_info.value
            expect(page.get_by_role("button",name="Confirm F1 connection",exact=True)).to_be_visible()
            expect(page.get_by_text("Connected",exact=True)).to_have_count(0)
            page.get_by_role("button",name="Confirm F1 connection",exact=True).click()
            expect(page.get_by_text("Connected",exact=True)).to_be_visible()
            popup.close()
            checks.append("simulated_verified_browser_access_requires_explicit_profile_confirmation")

            fake_connection={"status":"not_connected","connected":False,"persistent":False,"expires_at":None}
            catalog=[{"source":"fastf1","source_event_key":"2025:1","source_session_key":"2025:1:"+kind,"season_year":2025,"round_number":1,"event_name":"Australian Grand Prix","location":"Melbourne","session_name":kind,"scheduled_start_utc":"2025-03-16T04:00:00Z"} for kind in ("Practice 1","Qualifying","Race")]
            page.route("**/api/sessions/catalog?*",lambda route:route.fulfill(status=200,json=catalog))
            page.goto("http://127.0.0.1:4173/sessions?view=explorer&season=2025")
            page.get_by_label("Data source",exact=True).select_option("f1tv")
            page.locator(".sessions-catalog").get_by_role("button",name=__import__('re').compile(r"^Race\s")).click()
            expect(page.get_by_role("button",name="Load session",exact=True)).to_be_disabled()
            page.screenshot(path=str(ARTIFACTS/"session-f1-connection-required.png"),full_page=True)
            page.get_by_role("link",name="Connect F1 account",exact=True).click()
            expect(page.locator("#f1-connection")).to_be_focused()
            page.get_by_role("link",name="Return to your session selection",exact=False).click()
            expect(page.get_by_label("Season",exact=True)).to_have_value("2025")
            expect(page.get_by_label("Data source",exact=True)).to_have_value("f1tv")
            expect(page.get_by_role("heading",name="Race",exact=True)).to_be_visible()
            page.get_by_role("button",name="Use OpenF1 history",exact=True).click()
            expect(page.get_by_label("Data source",exact=True)).to_have_value("openf1")
            expect(page.get_by_role("button",name="Load session",exact=True)).to_be_enabled()
            checks.append("unlinked_f1_blocked_with_connector_round_trip_preserving_race_and_free_fallback")

            fake_connection={"status":"connected","connected":True,"persistent":True,"expires_at":expires}
            page.reload()
            page.get_by_label("Data source",exact=True).select_option("f1tv")
            page.route("**/api/sessions/import",lambda route:route.fulfill(status=424,json={"detail":{"code":"f1_source_access_denied","message":"F1 refused timing archive access; your password may be correct."}}))
            page.get_by_role("button",name="Load session",exact=True).click()
            expect(page.get_by_text("F1 refused timing archive access",exact=False)).to_be_visible()
            expect(page.get_by_role("link",name="Check F1 connection in Profile",exact=True)).to_be_visible()
            page.get_by_role("button",name="Use OpenF1 history",exact=True).click()
            expect(page.get_by_text("F1 refused timing archive access",exact=False)).to_have_count(0)
            checks.append("structured_import_error_keeps_actual_reason_and_offers_profile_or_openf1")
            page.unroute("**/api/profile",simulate_profile)
            page.unroute("**/api/profile/connections/f1",simulate_connection)
            page.route("**/api/profile/connections/f1",fail_connection)
            page.goto("http://127.0.0.1:4173/signup")
            page.get_by_label("Email",exact=True).fill("profile-e2e-"+secrets.token_hex(6)+"@example.com")
            page.get_by_label("Password",exact=True).fill(secrets.token_urlsafe(20))
            page.get_by_label("I have an F1 account",exact=False).check()
            page.get_by_label("F1 account email",exact=True).fill("f1-fixture@example.com")
            page.get_by_label("F1 account password",exact=True).fill("fixture-f1-password")
            page.get_by_label("Keep my connection using encrypted credentials",exact=False).check()
            page.get_by_role("button",name="Sign up",exact=True).click()
            page.wait_for_url("**/profile")
            expect(page.get_by_role("alert")).to_contain_text("Your PitWall account was created")
            token=page.evaluate("localStorage.getItem('auth_token')")
            users.append(api("/api/auth/session",token)["user_id"])
            expect(page.get_by_label("Display name")).to_have_value("")
            checks.append("signup_f1_failure_recovers_to_new_profile_without_leaking_previous_profile")
            assert not errors, errors
            browser.close()
    finally:
        cleanup = """import json,sys
from modules.storage.infrastructure.db import SessionLocal
from modules.identity_auth.infrastructure.db_models import UserRecord
with SessionLocal() as db:
    for user_id in json.load(sys.stdin):
        row=db.get(UserRecord,user_id)
        if row is not None and row.email.startswith('profile-e2e-'):
            db.delete(row)
    db.commit()
"""
        subprocess.run([str(ROOT/"backend/.venv/Scripts/python.exe"),"-c",cleanup],input=json.dumps(users),text=True,cwd=ROOT/"backend",check=True)
    report={"checks":checks,"count":len(checks),"browser_errors":errors,"f1_provider_responses_simulated":True,"profile_and_signup_used_real_database":True,"test_accounts_removed":True}
    (ARTIFACTS/"results.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
