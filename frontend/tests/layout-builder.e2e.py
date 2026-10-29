"""Live layout-builder regression tests. Requires Playwright, local API and an imported session."""
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
BASE = os.environ.get('PITWALL_FRONTEND_URL', 'http://127.0.0.1:5173')
API = 'http://127.0.0.1:8000'
ARTIFACTS = Path(tempfile.gettempdir()) / 'pitwall-layout-builder-e2e'
ARTIFACTS.mkdir(exist_ok=True)


def api(method, path, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = Request(API + path, data=json.dumps(data).encode() if data is not None else None, headers=headers, method=method)
    with urlopen(req, timeout=30) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def card(page, name):
    return page.locator('.builder-layout-card').filter(has_text=name)


def login(page, email, password):
    page.goto(BASE + '/login')
    page.get_by_label('Email', exact=True).fill(email)
    page.get_by_label('Password', exact=True).fill(password)
    page.get_by_role('button', name='Sign in', exact=True).click()
    page.locator('.app-header').get_by_role('button', name='Sign out', exact=True).wait_for()


def pointer_drag(page, handle, dx, dy):
    handle.scroll_into_view_if_needed()
    box = handle.bounding_box()
    if box['y'] < 240:
        page.evaluate('window.scrollBy(0,-260)')
        box = handle.bounding_box()
    x, y = box['x'] + box['width']/2, box['y'] + box['height']/2
    page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + dx, y + dy, steps=8); page.mouse.up()


created_ids = []
email = f'builder-e2e-{secrets.token_hex(8)}@example.com'
password = secrets.token_urlsafe(20)
auth = api('POST', '/api/auth/signup', {'email': email, 'password': password})
token = auth['access_token']
created_ids.append(api('GET', '/api/auth/session', token=token)['user_id'])
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        page = context.new_page(); errors = []; requests = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda req: requests.append(req.url))
        login(page, email, password)
        page.goto(BASE + '/dashboard-builder')
        expect(page.locator('.builder-layout-card')).to_have_count(3)
        expect(page.get_by_role('button', name='Edit layout', exact=True)).to_have_count(0)
        expect(page.get_by_role('button', name='Delete', exact=True)).to_have_count(0)
        expect(card(page, 'Session Trends').locator('[data-preview-kind="track"]')).to_have_count(1)
        expect(card(page, 'Session Trends').locator('[data-preview-kind="laps"]')).to_have_count(1)
        page.get_by_role('button', name='+ New layout', exact=True).click()
        page.get_by_role('button', name='Save layout', exact=True).click()
        expect(page.get_by_role('alert')).to_contain_text('name')
        page.get_by_label('Layout name', exact=True).fill('E2E race dashboard')
        page.get_by_label('Description', exact=True).fill('Live whole-dashboard test')
        expect(page.get_by_role('button', name='Add System Health', exact=True)).to_have_count(0)
        expect(page.get_by_role('button', name='Add Sessions', exact=True)).to_have_count(0)
        expect(page.get_by_label('Section', exact=True)).to_have_count(0)
        page.get_by_label('Search widgets', exact=True).fill('no matching panel')
        expect(page.get_by_text('No matching widgets.', exact=False)).to_be_visible()
        page.get_by_label('Search widgets', exact=True).fill('')
        for access in ['subscription', '1', '2', '3']:
            page.get_by_label('Widget access', exact=True).select_option(access)
            expect(page.locator('.editor-library__widget')).to_have_count(0)
        page.get_by_label('Widget access', exact=True).select_option('free')
        expect(page.locator('.editor-library__widget')).to_have_count(6)
        expect(page.locator('.editor-library__widget .widget-tier')).to_have_text(['Free'] * 6)
        assert set(page.locator('.editor-library__thumbnail [data-preview-kind]').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.previewKind)')) == {'trace','brake','pace','stints','laps','track'}
        first_group = page.get_by_test_id('editor-group').first
        first_group.get_by_label('Group title', exact=True).fill('Lap detail')
        page.locator('.editor-library__widget').filter(has_text='Lap Table').drag_to(first_group.get_by_test_id('editor-canvas'), target_position={'x': 20, 'y': 20})
        expect(first_group.get_by_test_id('editor-widget')).to_have_count(1)
        page.get_by_role('button', name='Add Telemetry Line Chart', exact=True).click()
        expect(first_group.get_by_test_id('editor-widget')).to_have_count(2)
        page.get_by_label('Metric',exact=True).select_option('throttle_pct')
        page.get_by_label('Panel title',exact=True).fill('Throttle detail')
        first = first_group.get_by_test_id('editor-widget').first
        first.get_by_role('button', name='Configure Lap Table', exact=True).click()
        step = first_group.get_by_test_id('editor-canvas').bounding_box()['width'] / 1200 * 60
        pointer_drag(page, first.get_by_role('button', name='Resize Lap Table', exact=True), -step * 7, -step * 4)
        expect(page.get_by_role('spinbutton', name='Panel w', exact=True)).to_have_value('4')
        expect(page.get_by_role('spinbutton', name='Panel h', exact=True)).to_have_value('4')
        first.get_by_role('button', name='Resize Lap Table', exact=True).focus()
        page.keyboard.press('ArrowLeft'); page.keyboard.press('ArrowUp')
        expect(page.get_by_role('spinbutton', name='Panel w', exact=True)).to_have_value('4')
        expect(page.get_by_role('spinbutton', name='Panel h', exact=True)).to_have_value('4')
        page.get_by_role('button', name='Undo', exact=True).click()
        expect(page.get_by_role('spinbutton', name='Panel w', exact=True)).to_have_value('6')
        expect(page.get_by_role('spinbutton', name='Panel h', exact=True)).to_have_value('6')
        pointer_drag(page, first.get_by_role('button', name='Resize Lap Table', exact=True), step * 3, 0)
        expect(page.get_by_role('spinbutton', name='Panel w', exact=True)).to_have_value('6')
        pointer_drag(page, first.get_by_role('button', name='Resize Lap Table', exact=True), 0, step)
        expect(page.get_by_role('spinbutton', name='Panel h', exact=True)).to_have_value('7')
        pointer_drag(page, first.get_by_role('button', name='Move Lap Table', exact=True), 0, step * 2)
        expect(page.get_by_role('spinbutton', name='Panel y', exact=True)).to_have_value('2')
        first.get_by_role('button', name='Move Lap Table', exact=True).focus(); page.keyboard.press('ArrowDown')
        expect(page.get_by_role('spinbutton', name='Panel y', exact=True)).to_have_value('3')
        page.get_by_role('button', name='Undo', exact=True).click()
        expect(page.get_by_role('spinbutton', name='Panel y', exact=True)).to_have_value('2')
        page.get_by_role('button', name='Redo', exact=True).click()
        page.get_by_role('spinbutton', name='Panel x', exact=True).fill('6')
        expect(page.get_by_role('alert')).to_contain_text('overlap')
        page.get_by_role('spinbutton', name='Panel w', exact=True).fill('3')
        expect(page.get_by_role('spinbutton', name='Panel w', exact=True)).to_have_value('4')
        expect(page.get_by_role('alert')).to_have_count(0)
        expect(first.locator('.widget-blueprint')).to_have_attribute('data-preview-mode','compact')
        page.get_by_role('spinbutton', name='Panel w', exact=True).fill('6')
        expect(first.locator('.widget-blueprint')).to_have_attribute('data-preview-mode','comfortable')
        page.get_by_label('Panel title', exact=True).fill('Race lap data')
        page.get_by_role('button', name='Duplicate panel', exact=True).click()
        expect(first_group.get_by_test_id('editor-widget')).to_have_count(3)
        first_group.get_by_test_id('editor-widget').last.get_by_role('button', name='Remove Race lap data', exact=True).click()
        page.get_by_role('button', name='+ Group', exact=True).click()
        second_group = page.get_by_test_id('editor-group').nth(1)
        second_group.get_by_label('Group title', exact=True).fill('Strategy')
        page.get_by_role('button', name='Add Stint Analysis', exact=True).click()
        expect(first_group).to_be_visible(); expect(second_group).to_be_visible()
        expect(page.get_by_test_id('editor-widget')).to_have_count(3)
        expect(page.get_by_role('spinbutton', name='Panel w', exact=True)).to_have_value('12')
        expect(page.get_by_role('spinbutton', name='Panel h', exact=True)).to_have_value('7')
        page.get_by_role('spinbutton', name='Panel h', exact=True).fill('20')
        expect(page.get_by_role('spinbutton', name='Panel h', exact=True)).to_have_value('14')
        page.get_by_role('spinbutton', name='Panel h', exact=True).fill('7')
        pointer_drag(page, second_group.get_by_role('button', name='Resize Stint Analysis', exact=True), 0, step * 10)
        expect(page.get_by_role('spinbutton', name='Panel h', exact=True)).to_have_value('14')
        page.get_by_role('spinbutton', name='Panel h', exact=True).fill('7')
        page.get_by_role('button', name='Move group 2 up', exact=True).click()
        expect(page.get_by_test_id('editor-group').first.get_by_role('heading', name='Strategy', exact=True)).to_be_visible()
        page.get_by_role('button', name='Move group 1 down', exact=True).click()
        page.get_by_role('button', name='+ Group', exact=True).click()
        page.get_by_role('button', name='Remove group 3', exact=True).click()
        expect(page.get_by_test_id('editor-group')).to_have_count(2)
        page.get_by_role('button', name='Whole dashboard', exact=True).click()
        overview = page.get_by_test_id('whole-dashboard-preview')
        expect(overview.get_by_role('img')).to_be_visible()
        expect(overview.locator('[data-preview-kind="stints"]')).to_have_count(1)
        expect(overview.locator('[data-preview-kind="laps"]')).to_have_count(1)
        expect(overview.locator('svg text').filter(has_text='Lap detail')).to_have_count(1)
        expect(overview.locator('svg text').filter(has_text='Strategy')).to_have_count(1)
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(ARTIFACTS / 'whole-dashboard.png'), full_page=True)
        page.get_by_role('button', name='Arrange panels', exact=True).click()
        page.locator('.app-header__nav').get_by_role('link', name='Home', exact=True).click()
        expect(page.get_by_text('You have unsaved changes. Leave this editor?', exact=True)).to_be_visible()
        page.get_by_role('button', name='Keep editing', exact=True).click()
        for width in [390, 768, 1280, 1600]:
            page.set_viewport_size({'width': width, 'height': 1000})
            assert page.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth'), f'editor overflow {width}'
            expect(page.get_by_test_id('editor-group')).to_have_count(2)
        page.set_viewport_size({'width': 390,'height': 1000}); page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(ARTIFACTS / 'editor-mobile.png'), full_page=True)
        page.set_viewport_size({'width': 1440,'height': 1000}); page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(ARTIFACTS / 'editor-desktop.png'), full_page=True)
        assert not [url for url in requests if urlparse(url).path.startswith(('/api/sessions','/api/telemetry/'))], 'Preview must not request telemetry'
        page.route('**/api/layouts', lambda route: route.fulfill(status=503,json={'detail':'Temporary save failure'},headers={'Access-Control-Allow-Origin':'*'}) if route.request.method=='POST' else route.continue_())
        page.get_by_role('button',name='Save layout',exact=True).click()
        expect(page.get_by_role('alert')).to_contain_text('Temporary save failure')
        page.unroute('**/api/layouts'); page.get_by_role('button',name='Save layout',exact=True).click()
        expect(page.get_by_role('region',name='Layout editor')).to_have_count(0)
        persisted = next(item for item in api('GET','/api/layouts',token=token) if item['name']=='E2E race dashboard')
        assert [group['title'] for group in persisted['config']['sections']] == ['Lap detail','Strategy']
        assert persisted['config']['sections'][0]['layout']['children'][0]['placement']=={'x':0,'y':3,'w':6,'h':7}
        print('PASS session-only catalog, all preview types, scaled drag/resize, minimum/ratio rules, compact blueprints, groups visible/reordered, whole picture, no preview telemetry, save retry and persistence',flush=True)
        card(page,'E2E race dashboard').get_by_role('button',name='Edit layout',exact=True).click()
        page.get_by_label('Layout name',exact=True).fill('E2E edited dashboard')
        page.get_by_label('Description',exact=True).fill('')
        page.get_by_role('button',name='Save layout',exact=True).click()
        expect(card(page,'E2E edited dashboard')).to_be_visible()
        personal = api('GET','/api/layouts',token=token)
        assert len(personal)==1 and personal[0]['id']==persisted['id'] and personal[0]['description'] is None
        page.route('**/api/layouts/favorites',lambda route:route.fulfill(status=503,json={'detail':'Favorite failed'},headers={'Access-Control-Allow-Origin':'*'}) if route.request.method=='PUT' else route.continue_())
        page.get_by_role('button',name='Favorite E2E edited dashboard',exact=True).click()
        expect(page.get_by_role('status')).to_contain_text('Could not update favorites')
        expect(page.get_by_role('button',name='Favorite E2E edited dashboard',exact=True)).to_have_attribute('aria-pressed','false')
        page.unroute('**/api/layouts/favorites')
        page.get_by_role('button',name='Favorite E2E edited dashboard',exact=True).click()
        expect(page.get_by_role('button',name='Unfavorite E2E edited dashboard',exact=True)).to_be_visible()
        page.reload(); expect(page.locator('.builder-layout-card').first).to_contain_text('E2E edited dashboard')
        factory = card(page,'Compare Lap')
        expect(factory.get_by_role('button',name='Edit layout',exact=True)).to_have_count(0)
        factory.get_by_role('button',name='Use template',exact=True).click()
        expect(page.get_by_test_id('editor-widget')).to_have_count(3)
        page.get_by_label('Layout name',exact=True).fill('E2E template copy')
        page.get_by_role('button',name='Save layout',exact=True).click()
        expect(card(page,'E2E template copy')).to_be_visible()
        sessions=api('GET','/api/sessions',token=token)
        existing=next((session for session in sessions if session.get('entry_count',0)),None)
        assert existing, 'An imported session is required for runtime tests'
        page.goto(BASE+'/sessions/'+existing['id']+'?mode=lookback&lap=all')
        expect(page.locator('.sessions-layout-item').first).to_contain_text('E2E edited dashboard')
        page.locator('.sessions-layout-item').first.locator('.sessions-layout-card').click()
        page.locator('.sessions-driver-chip').first.click()
        expect(page.locator('.layout-group--grid')).to_have_count(2)
        frame=page.locator('.responsive-widget[data-widget="lap-table"]')
        frame.evaluate('(e)=>{e.style.width="360px";e.style.flex="0 0 360px";e.style.height="280px"}')
        expect(frame).to_have_attribute('data-density','compact')
        expect(frame).to_have_attribute('data-height','short')
        expect(frame.locator('.telemetry-table__header > :nth-child(4)')).to_have_css('display','none')
        frame.evaluate('(e)=>{e.style.width="600px";e.style.flex="0 0 600px";e.style.height="500px"}')
        expect(frame).to_have_attribute('data-density','comfortable')
        expect(frame.locator('.telemetry-table__header > :nth-child(4)')).not_to_have_css('display','none')
        frame.evaluate('(e)=>e.removeAttribute("style")')
        strategy_frame=page.locator('.responsive-widget[data-widget="stint-analysis"]')
        strategy_frame.evaluate('(e)=>{e.style.width="594px";e.style.flex="0 0 594px";e.style.height="280px"}')
        expect(strategy_frame).to_have_attribute('data-height','short')
        expect(strategy_frame.locator('.stint-details')).not_to_have_attribute('open','')
        strategy_frame.locator('.stint-details > summary').click()
        expect(strategy_frame.locator('.stint-details')).to_have_attribute('open','')
        strategy_frame.evaluate('(e)=>e.removeAttribute("style")')
        page.evaluate('window.scrollTo(0,0)'); page.screenshot(path=str(ARTIFACTS/'session-grid.png'),full_page=True)
        page.get_by_role('button',name='Unfavorite E2E edited dashboard',exact=True).click()
        expect(page.get_by_role('button',name='Favorite E2E edited dashboard',exact=True)).to_be_visible()
        page.set_viewport_size({'width':390,'height':1000})
        expect(page.locator('.layout-group--grid').first).to_have_css('display','flex')
        assert page.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth')
        page.set_viewport_size({'width':1440,'height':1000})
        print('PASS edit/reload, factory copy, favorites in session order, real lap/strategy rendering, per-panel compact/short adaptation and mobile stacking',flush=True)
        page.goto(BASE+'/dashboard-builder?audience=live-race')
        page.get_by_role('button',name='+ New layout',exact=True).click()
        expect(page.locator('.editor-library__widget')).to_have_count(3)
        page.get_by_role('button',name='Add Replay Track Map',exact=True).click()
        page.get_by_label('Layout name',exact=True).fill('E2E replay dashboard')
        page.get_by_role('button',name='Save layout',exact=True).click()
        expect(card(page,'E2E replay dashboard')).to_be_visible()
        card(page,'E2E replay dashboard').get_by_role('button',name='Edit layout',exact=True).click()
        page.get_by_label('Layout name',exact=True).fill('Unsaved')
        page.once('dialog',lambda dialog:dialog.dismiss()); page.get_by_role('button',name='Cancel',exact=True).click()
        expect(page.get_by_role('region',name='Layout editor')).to_be_visible()
        page.once('dialog',lambda dialog:dialog.accept()); page.get_by_role('button',name='Cancel',exact=True).click()
        page.route('**/api/layouts/*',lambda route:route.fulfill(status=503,json={'detail':'Delete failed'},headers={'Access-Control-Allow-Origin':'*'}) if route.request.method=='DELETE' else route.continue_())
        page.once('dialog',lambda dialog:dialog.accept()); card(page,'E2E replay dashboard').get_by_role('button',name='Delete',exact=True).click()
        expect(page.get_by_role('status')).to_contain_text('Could not delete')
        expect(card(page,'E2E replay dashboard')).to_be_visible()
        page.unroute('**/api/layouts/*')
        page.once('dialog',lambda dialog:dialog.accept()); card(page,'E2E replay dashboard').get_by_role('button',name='Delete',exact=True).click()
        expect(card(page,'E2E replay dashboard')).to_have_count(0)
        page.goto(BASE+'/dashboard-builder')
        seed={key:persisted[key] for key in ['name','description','audience','schemaVersion','config']}
        for index in range(12):api('POST','/api/layouts',{**seed,'name':f'E2E extra {index}'},token)
        page.reload(); expect(page.locator('.builder-layout-card')).to_have_count(17)
        page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
        assert 0<=page.get_by_role('button',name='+ New layout',exact=True).bounding_box()['y']<=300
        second_email=f'builder-e2e-{secrets.token_hex(8)}@example.com'; second_password=secrets.token_urlsafe(20)
        second_auth=api('POST','/api/auth/signup',{'email':second_email,'password':second_password})
        created_ids.append(api('GET','/api/auth/session',token=second_auth['access_token'])['user_id'])
        page.locator('.app-header').get_by_role('button',name='Sign out',exact=True).click()
        login(page,second_email,second_password); page.goto(BASE+'/dashboard-builder')
        expect(page.locator('.builder-layout-card')).to_have_count(3)
        expect(page.locator('.layout-favorite.is-favorite')).to_have_count(0)
        assert not errors,errors
        print('PASS replay eligibility, discard/delete, sticky creation with 17 layouts, account cache isolation, no browser runtime errors',flush=True)
        browser.close()
finally:
    cleanup="from modules.storage.infrastructure.db import SessionLocal; from modules.identity_auth.infrastructure.db_models import UserRecord; import sys; db=SessionLocal(); row=db.get(UserRecord,sys.argv[1]); assert row is not None and row.email.startswith('builder-e2e-'); db.delete(row); db.commit(); db.close()"
    for user_id in created_ids:
        subprocess.run([str(ROOT/'backend/.venv/Scripts/python.exe'),'-c',cleanup,user_id],cwd=ROOT/'backend',check=True)
print('Temporary accounts cleaned up. Screenshots:',ARTIFACTS)
