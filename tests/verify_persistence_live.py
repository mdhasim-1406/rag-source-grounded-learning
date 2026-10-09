"""Standalone real-provider persistence smoke; owns server and disposable DB."""
import os, subprocess, time, tempfile, json, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8023'
data=tempfile.mkdtemp(prefix='scholar-history-',dir=os.environ.get('TMPDIR',str(Path.home()/'.hermes/cache/scratch')))
env=dict(os.environ,DATA_DIR=data,PYTHONPATH=str(ROOT/'backend'))
server=None

def start():
    global server
    server=subprocess.Popen([str(ROOT/'.venv/bin/uvicorn'),'app.main:app','--host','127.0.0.1','--port','8023'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for _ in range(80):
        try: urllib.request.urlopen(BASE+'/health',timeout=1); return
        except Exception: time.sleep(.15)
    raise RuntimeError('owned test backend failed startup')
def stop():
    global server
    if server:
        server.terminate();server.wait(timeout=10);server=None

try:
    start()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1600,'height':1000})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE,wait_until='networkidle')
        page.click('#btnTextModal')
        page.fill('#noteTitleInput','Memory Systems')
        page.fill('#noteContentInput','Virtual memory maps virtual addresses to physical memory. Page tables store these mappings. A translation lookaside buffer caches recent address translations to reduce access latency. A page fault occurs when a referenced page is not resident in physical memory.')
        page.click('#btnSubmitNote');expect(page.get_by_text('Memory Systems',exact=True)).to_be_visible(timeout=15000)
        page.locator('.source-checkbox').first.check()
        page.click('#btnClearChat')
        expect(page.locator('#chatSessionSelect option')).to_have_count(1,timeout=10000)
        page.wait_for_function("state.activeSessionId !== null")
        for query in ['What does a translation lookaside buffer do?','How does it help with the operation you just described?']:
            page.fill('#queryInput',query)
            with page.expect_response(lambda r: r.url == BASE+'/api/v1/chat' and r.request.method == 'POST', timeout=120000) as pending:
                page.click('#btnSendQuery')
            response=pending.value
            assert response.status==200, response.text()
            expect(page.locator('#btnSendQuery')).to_be_enabled(timeout=120000)
        expect(page.locator('.message-user')).to_have_count(2)
        expect(page.locator('.message-assistant')).to_have_count(3)  # welcome plus two replies
        sid=page.locator('#chatSessionSelect').input_value()
        ws=page.locator('#workspaceSelect').input_value()
        before=page.request.get(f'{BASE}/api/v1/chat/sessions/{sid}?workspace_id={ws}').json()
        assert len(before['messages'])==4,before
        page.reload(wait_until='networkidle')
        expect(page.locator('.message-user')).to_have_count(2,timeout=10000)
        expect(page.locator('.citation-pill').first).to_be_visible()
        page.locator('.citation-pill').first.click();expect(page.locator('#citationModal')).to_have_class('modal-overlay active')
        page.locator('#citationModal button').click()
        page.get_by_role('button',name='Study Guide',exact=True).click();page.click('#btnSynthesizeGuide')
        expect(page.locator('#studyGuideContent h3')).to_be_visible(timeout=120000)
        guides=page.request.get(f'{BASE}/api/v1/study/guides?workspace_id={ws}').json();assert guides
        stop();start()
        page.reload(wait_until='networkidle')
        expect(page.locator('.message-user')).to_have_count(2,timeout=10000)
        after=page.request.get(f'{BASE}/api/v1/chat/sessions/{sid}?workspace_id={ws}').json()
        assert [m['id'] for m in before['messages']]==[m['id'] for m in after['messages']]
        restored=page.request.get(f'{BASE}/api/v1/study/guides?workspace_id={ws}').json()
        assert guides[0]['id']==restored[0]['id']
        assert not errors,errors
        print(json.dumps({'live_provider':True,'messages_saved':4,'refresh_restored':True,'restart_same_message_ids':True,'guide_survived_restart':True,'browser_errors':errors,'isolated_data':data},indent=2))
        browser.close()
finally: stop()
