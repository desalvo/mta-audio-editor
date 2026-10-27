"""General phase controls in genuine Chromium; actual API/journal/conservation."""
import os

import pytest
from app import auth
from test_r210_admin_cutover_e2e import ready as ready, account as account, BASE, HEADERS  # noqa: F401
from test_r210_admin_cutover_browser import browser_session
from test_r210_transition_progress import reserve_actual, committed_actual


def check_layout(page):
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert page.locator('[data-cutover-progress][role=status]').count()==1


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_reserved_cancel_keyboard_confirmation_actor_audit(ready,chromium_capability,language,width):
    from playwright.sync_api import sync_playwright,expect
    key=reserve_actual(ready)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        page,errors,posts=browser_session(ready[0],language,browser,width)
        expect(page.locator('[data-cutover-progress]')).to_contain_text(key)
        cancel=page.locator('[data-cutover-abort]');expect(cancel).to_be_visible()
        page.once('dialog',lambda dialog:dialog.dismiss());cancel.click();assert posts==[]
        page.once('dialog',lambda dialog:dialog.accept());cancel.focus();page.keyboard.press('Enter')
        expect(page.locator('[data-cutover-progress]')).to_contain_text('Nessun passaggio attivo' if language=='it' else 'No active transition')
        expect(page.locator('[data-cutover-audit]')).to_contain_text('annullata' if language=='it' else 'cancelled')
        assert posts==[(BASE+'/reservations/'+key+'/abort',{'expected_revision':0,'confirm':True})]
        assert ready[0].get(BASE+'/lifecycle').json()['items'][0]['events'][0]['actor_id']==ready[2]
        assert not errors;check_layout(page);browser.close()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('damage',['mirror','legacy','conflict','disabled'])
def test_unverified_and_legacy_commits_show_reason_without_unsafe_controls(ready,monkeypatch,chromium_capability,language,damage):
    from playwright.sync_api import sync_playwright,expect
    if damage=='legacy':
        from app.regime_balance_continuity import commit_preserving_balances
        from app import regime_admin_cutover as cutover
        key=reserve_actual(ready)
        with auth.db() as con:
            con.execute('BEGIN IMMEDIATE')
            commit_preserving_balances(con,transition_id=key,expected_revision=0,readiness_check=lambda c:bool(cutover.audit(c)))
    else:
        body=committed_actual(ready,monkeypatch);key=body['request_id']
        if damage=='disabled':monkeypatch.setenv('MTA_REGIME_CUTOVER','off')
        elif damage=='mirror':(auth.data_root()/'service-regime.json').write_text('{"regime":"COMMERCIAL","revision":99}')
        else:
            import sqlite3
            with sqlite3.connect(auth.db_path()) as con:con.execute('UPDATE regime_fence_state SET revision=99')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        page,errors,posts=browser_session(ready[0],language,browser,390)
        expect(page.locator('[data-cutover-progress]')).to_contain_text('manutenzione' if damage=='legacy' and language=='it' else 'maintenance' if damage=='legacy' else 'Recupero locale non attivo' if damage=='disabled' and language=='it' else 'Local recovery inactive' if damage=='disabled' else 'Prove originali' if language=='it' else 'Original evidence')
        expect(page.locator('[data-cutover-abort]')).to_be_hidden()
        for button in page.locator('[data-cutover-recovery]').all():expect(button).to_be_disabled()
        assert posts==[] and not errors;check_layout(page);browser.close()


@pytest.mark.parametrize('language',['it','en'])
def test_failed_progress_read_clears_actions_and_refresh_recovers(ready,chromium_capability,language):
    from playwright.sync_api import sync_playwright,expect
    reserve_actual(ready);fail=[True]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        page,errors,posts=browser_session(ready[0],language,browser,390,fail_lifecycle=fail)
        expect(page.locator('[data-cutover-progress]')).to_contain_text('non disponibile' if language=='it' else 'unavailable')
        expect(page.locator('[data-cutover-abort]')).to_be_hidden()
        fail[0]=False
        page.get_by_role('button',name='Aggiorna registro' if language=='it' else 'Refresh transition audit',exact=True).click()
        expect(page.locator('[data-cutover-abort]')).to_be_visible()
        assert posts==[] and not errors;browser.close()


def test_progress_poll_follows_independent_cancellation_without_mutating(ready,chromium_capability):
    from playwright.sync_api import sync_playwright,expect
    key=reserve_actual(ready)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        page,errors,posts=browser_session(ready[0],'en',browser,390)
        expect(page.locator('[data-cutover-abort]')).to_be_visible()
        assert ready[0].post(BASE+'/reservations/'+key+'/abort',headers=HEADERS,json={'expected_revision':0,'confirm':True}).status_code==200
        expect(page.locator('[data-cutover-progress]')).to_contain_text('No active transition',timeout=8000)
        expect(page.locator('[data-cutover-abort]')).to_be_hidden()
        assert posts==[] and not errors;browser.close()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
@pytest.mark.parametrize('phase',['idle','committed'])
def test_full_shipped_settings_progress_accessibility(ready,monkeypatch,chromium_capability,language,width,phase):
    from playwright.sync_api import sync_playwright,expect
    from test_r210_account_acceptance import serve
    supplied=os.environ.get('MTA_TEST_AXE_CORE')
    if not supplied:pytest.skip('Pinned test-only axe-core required')
    web,_,actor=ready
    with auth.db() as con:con.execute('UPDATE users SET language=? WHERE id=?',(language,actor))
    if phase=='committed':committed_actual(ready,monkeypatch)
    from fastapi.testclient import TestClient
    from app import main
    from test_r210_legal_documents import cookie
    web=TestClient(main.app,raise_server_exceptions=False);web.cookies.update(cookie(actor))
    calls=[];errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls))
        page.goto('https://mta.test/settings');page.wait_for_load_state('networkidle')
        expect(page.locator('[data-cutover-progress]')).to_contain_text(('Nessun passaggio attivo' if language=='it' else 'No active transition') if phase=='idle' else ('in attesa del recupero' if language=='it' else 'pending recovery'))
        if phase=='committed':
            page.once('dialog',lambda dialog:dialog.accept())
            recover=page.locator('[data-cutover-recovery]');expect(recover).to_be_enabled();recover.focus();page.keyboard.press('Enter')
            expect(page.locator('[data-cutover-progress]')).to_contain_text('Nessun passaggio attivo' if language=='it' else 'No active transition')
        assert page.locator('[data-regime-cutover]').count()==1
        page.add_script_tag(path=supplied)
        result=page.evaluate("async()=>{const r=await axe.run(document.querySelector('[data-regime-cutover]'));return r.violations.map(x=>({id:x.id,nodes:x.nodes.map(n=>n.target)}))}")
        assert result==[],result
        assert not errors;check_layout(page)
        assert any(path==BASE+'/lifecycle' and status==200 for _,path,status in calls)
        browser.close()
