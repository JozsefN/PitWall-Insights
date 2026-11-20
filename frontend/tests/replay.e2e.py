"""Real replay startup, playback, seeking, source failure and active-token renewal."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]

import sys
sys.path.insert(0, str(ROOT / 'scripts'))
from local_test_accounts import seed_verified_account
BASE = os.environ.get('PITWALL_FRONTEND_URL', 'http://127.0.0.1:5173')
PYTHON = ROOT / 'backend/.venv/Scripts/python.exe'
ARTIFACTS = Path(tempfile.gettempdir()) / 'pitwall-replay-e2e'
ARTIFACTS.mkdir(exist_ok=True)
token = None
user_id = None

def api(path, data=None):
    headers = {'Content-Type': 'application/json'}
    if token: headers['Authorization'] = 'Bearer ' + token
    with urlopen(Request('http://127.0.0.1:8000'+path, data=json.dumps(data).encode() if data is not None else None, headers=headers), timeout=30) as response:
        return json.loads(response.read())

def mint(minutes):
    code = f"from modules.identity_auth.application.security import SECRET_KEY,ALGORITHM;from jose import jwt;from datetime import datetime,timedelta,timezone;print(jwt.encode({{'sub':{user_id!r},'email':{email!r},'exp':datetime.now(timezone.utc)+timedelta(minutes={minutes})}},SECRET_KEY,algorithm=ALGORITHM))"
    return subprocess.check_output([str(PYTHON), '-c', code], cwd=ROOT/'backend', text=True).strip()

def replay_url(session_id, entries):
    return BASE + f'/sessions/{session_id}?' + urlencode({'mode':'simulation','layout':'builtin:replay-focus','drivers':','.join(entry['id'] for entry in entries),'lap':'all'})

try:
    email = f'replay-browser-{secrets.token_hex(8)}@example.com'
    token = seed_verified_account({'email':email,'password':secrets.token_urlsafe(24)})['access_token']
    user_id = api('/api/auth/session')['user_id']
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width':1440,'height':1000})
        requests = []; errors = []
        page.on('request',lambda request: requests.append(request.url))
        page.on('pageerror',lambda error:errors.append(str(error)))
        near_expiry = mint(2)
        page.goto(BASE+'/login')
        page.evaluate('(token)=>localStorage.setItem("auth_token",token)',near_expiry)
        race = api('/api/sessions/import', {
            'season_year': 2025,
            'round_number': 7,
            'session_name': 'Race',
            'source_session_key': 'openf1:session:9987',
            'import_profile': 'core',
        })
        session_id = race['id']
        entries = api(f'/api/sessions/{session_id}/entries')
        assert len(entries) == 20, 'The Imola full-grid fixture should have 20 drivers'
        started = monotonic()
        page.goto(replay_url(session_id,entries))
        start = page.get_by_role('button',name='Start',exact=True)
        expect(start).to_be_enabled(timeout=180000)
        # The timing feed can begin before the first location sample. Jump into the race
        # to check the full field without accidentally requiring future positions to render.
        page.get_by_label('Jump to lap',exact=True).select_option(label='Lap 3')
        expect(page.locator('.track-map-viewer__driver-dot')).to_have_count(20,timeout=30000)
        expect(page.locator('.replay-driver-card')).to_have_count(20,timeout=30000)
        startup = monotonic()-started
        zoom_in = page.get_by_role('button',name='Zoom in',exact=True)
        for _ in range(7):
            if page.locator('.track-map-car').count():
                break
            zoom_in.click()
        expect(page.locator('.track-map-car')).to_have_count(20)
        assert startup < 180, f'Cached browser startup exceeded 180s: {startup}'
        assert sum('/api/auth/refresh' in url for url in requests)==1,'Concurrent requests should share one renewal'
        assert not any('/ticks?' in url for url in requests),'Replay should use the compact timeline'
        telemetry_requests = [url for url in requests if '/telemetry/position' in url or '/telemetry/car' in url]
        assert telemetry_requests and all('sample_interval_ms=' in url for url in telemetry_requests)
        slider = page.locator('.sessions-replay-timeline input[type=range]')
        before = int(slider.input_value())
        marker = page.locator('.track-map-car').first
        before_marker = marker.get_attribute('transform')
        page.get_by_role('button',name='Start',exact=True).click()
        page.wait_for_function('(start)=>Number(document.querySelector(".sessions-replay-timeline input").value)>start+500',arg=before)
        page.get_by_role('button',name='Pause',exact=True).click()
        page.wait_for_function('(before)=>document.querySelector(".track-map-car").getAttribute("transform")!==before',arg=before_marker)
        slider.focus(); page.keyboard.press('End')
        expect(slider).to_have_value(slider.get_attribute('max'))
        # Retired drivers and other stale positions must not remain on the circuit.
        assert page.locator('.track-map-car').count() <= len(entries)
        expect(page.locator('.track-map-viewer')).to_be_visible()
        expect(page.locator('.widget-state--error')).to_have_count(0)
        page.locator('.track-map-viewer').scroll_into_view_if_needed()
        page.screenshot(path=str(ARTIFACTS/'cached-replay.png'))
        print(f'PASS cached replay with 20 drivers playable in {startup:.2f}s; one token renewal, sampled full-race coverage, playback and seek-to-end',flush=True)

        started = monotonic()
        # Exercise empty telemetry without relying on an obsolete provider or an upstream outage.
        empty_car = '**/telemetry/car?*'
        page.route(empty_car, lambda route: route.fulfill(
            status=200, json=[], headers={'Access-Control-Allow-Origin': BASE},
        ))
        page.goto(replay_url(session_id, entries[:2]))
        status = page.locator('#replay-start-status')
        expect(status).to_contain_text('Car telemetry is missing for 2 drivers',timeout=60000)
        expect(start).to_be_disabled()
        start.evaluate('node => node.click()')
        expect(page.get_by_role('button',name='Pause',exact=True)).to_have_count(0)
        failure_seconds = monotonic()-started
        status.scroll_into_view_if_needed()
        page.screenshot(path=str(ARTIFACTS/'source-unavailable.png'))
        page.unroute(empty_car)
        page.reload()
        expect(start).to_be_enabled(timeout=60000)
        print(f'PASS empty telemetry blocked replay in {failure_seconds:.2f}s and real data restored playback',flush=True)

        page.evaluate('(token)=>localStorage.setItem("auth_token",token)',mint(-1))
        page.reload()
        expect(page.get_by_text('Login required',exact=True)).to_be_visible(timeout=15000)
        assert page.evaluate('localStorage.getItem("auth_token")') is None
        assert not errors, errors
        print('PASS expired token returns to sign-in; no browser runtime errors',flush=True)
        (ARTIFACTS/'results.json').write_text(json.dumps({'cached_20_driver_browser_startup_seconds':round(startup,3),'simulated_empty_telemetry_seconds':round(failure_seconds,3)},indent=2),encoding='utf-8')
        browser.close()
finally:
    if user_id:
        code = f"from modules.storage.infrastructure.db import SessionLocal;from modules.identity_auth.infrastructure.db_models import UserRecord;db=SessionLocal();db.query(UserRecord).filter(UserRecord.id=={user_id!r}).delete();db.commit();db.close()"
        subprocess.run([str(PYTHON),'-c',code],cwd=ROOT/'backend',check=True)
