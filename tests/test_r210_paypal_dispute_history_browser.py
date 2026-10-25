"""Shipped owner pages / administrator controls -> real API/SQLite, GET-only."""
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from app import auth,resource_accounts as resources
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_account_acceptance import client,serve,assert_accessible_owner_page
from test_r210_paypal_dispute_history import fixture,report


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
@pytest.mark.parametrize('path',['/account','/account/credits'])
def test_owner_full_page_discovers_holds_then_resolves_without_webhook_or_collection(account,provider,monkeypatch,nc_browser_config,language,width,path):
    from playwright.sync_api import sync_playwright
    local,_,documents,remote_calls,_=fixture(account,provider,monkeypatch,paid=True,multi=True)
    with auth.db() as c:c.execute('UPDATE users SET language=?,limits_expanded=1 WHERE id=?',(language,account))
    web=client(account,monkeypatch);calls=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls));page.goto('https://mta.test'+path)
        panel=page.locator('[data-owner-payments]');button=panel.get_by_role('button',name='Verifica esito senza incassare' if language=='it' else 'Verify status without collecting payment');button.wait_for()
        page.once('dialog',lambda d:d.dismiss());button.click();assert not remote_calls
        page.once('dialog',lambda d:d.accept())
        with page.expect_response(lambda r:r.url.endswith('/verify') and r.request.method=='POST') as response:button.click()
        assert response.value.status==200
        held=panel.get_by_text('Fondi del pagamento trattenuti o stornati:' if language=='it' else 'Payment funds held or reversed:',exact=False);held.wait_for()
        assert resources.state(account)['credits_micro']==0 and report()['positions'][0]['held_minor']==500
        assert 'PP-D-123' not in panel.inner_text() and 'CAPTURE111' not in panel.inner_text()
        # Provider-protection payout cannot be called a verified release.
        documents['PP-D-123'].update(status='RESOLVED',update_time='2026-10-24T02:00:00Z',dispute_outcome={'outcome_code':'RESOLVED_WITH_PAYOUT'})
        page.once('dialog',lambda d:d.accept());button.click()
        panel.get_by_text('Sono registrate prove finanziarie' if language=='it' else 'Unresolved financial evidence',exact=False).wait_for()
        assert resources.state(account)['credits_micro']==0 and report()['pending']==2
        documents['PP-D-123'].update(update_time='2026-10-24T03:00:00Z',dispute_outcome={'outcome_code':'RESOLVED_SELLER_FAVOUR'})
        page.once('dialog',lambda d:d.accept());button.click()
        page.wait_for_function("!document.querySelector('[data-owner-payments]').textContent.includes("+repr('Fondi del pagamento' if language=='it' else 'Payment funds held')+") && !document.querySelector('[data-owner-payments] button').disabled")
        assert resources.state(account)['credits_micro']==5_000_000 and report()['pending']==0
        if path=='/account':
            page.wait_for_function("document.querySelector('[data-resource-account] .credits-total')?.textContent.includes('5')")
        assert_accessible_owner_page(page);assert not errors and all(code<400 for _,_,code in calls)
        assert not any('/capture' in url or url.endswith('/checkout') for _,url,_ in calls)
        # NC retains the local history/risk information but denies reconciliation.
        with auth.db() as c:c.execute("UPDATE regime_fence_state SET regime='NON_COMMERCIAL'")
        (auth.data_root()/'service-regime.json').write_text(json.dumps({'regime':'NON_COMMERCIAL','revision':0}))
        before=len(remote_calls);page.reload();panel.get_by_text(local,exact=False).wait_for()
        assert panel.get_by_role('button',name='Verifica esito senza incassare' if language=='it' else 'Verify status without collecting payment').count()==0 and len(remote_calls)==before
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_owner_gap_error_refresh_and_actual_recovery(account,provider,monkeypatch,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    _,_,_,_,hook=fixture(account,provider,monkeypatch,paid=True)
    with auth.db() as c:c.execute('UPDATE users SET language=? WHERE id=?',(language,account))
    def error(cfg,path):
        if path.startswith('/v1/customer/disputes?'):raise ValueError('Simulated unavailable Disputes permission')
    hook['run']=error;web=client(account,monkeypatch);calls=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000});page.route('**/*',serve(web,calls));page.goto('https://mta.test/account/credits')
        panel=page.locator('[data-owner-payments]');button=panel.get_by_role('button',name='Verifica esito senza incassare' if language=='it' else 'Verify status without collecting payment');button.wait_for()
        page.once('dialog',lambda d:d.accept());button.click()
        panel.get_by_text('Storico pagamenti non disponibile' if language=='it' else 'Payment history unavailable',exact=False).wait_for()
        assert button.count()==0 and resources.state(account)['credits_micro']==5_000_000 and report()['pending']==1
        panel.get_by_role('button',name='Aggiorna storico' if language=='it' else 'Refresh history').click()
        panel.get_by_text('Sono registrate prove finanziarie' if language=='it' else 'Unresolved financial evidence',exact=False).wait_for()
        hook['run']=None;page.once('dialog',lambda d:d.accept());button.click()
        panel.get_by_text('Fondi del pagamento trattenuti o stornati:' if language=='it' else 'Payment funds held or reversed:',exact=False).wait_for()
        assert resources.state(account)['credits_micro']==3_000_000 and report()['pending']==0
        assert_accessible_owner_page(page);browser.close()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_admin_actual_history_reconciliation_feedback_and_held_money(account,provider,monkeypatch,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    local,_,documents,_,_=fixture(account,provider,monkeypatch,paid=True)
    documents['PP-D-123'].update(status='RESOLVED',dispute_outcome={'outcome_code':'RESOLVED_WITH_PAYOUT'})
    web=client(auth.find_user('admin')['id'],monkeypatch);calls=[];errors=[]
    def route(route):
        url=urlsplit(route.request.url);assert url.hostname=='mta.test'
        if url.path=='/history-admin':
            route.fulfill(content_type='text/html',body='<html lang="'+language+'"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{overflow-wrap:anywhere}button{max-width:100%}table{font-size:.7em}</style><main id="serviceRegimePanel"></main></html>');return
        return serve(web,calls)(route)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',route);page.goto('https://mta.test/history-admin')
        page.add_script_tag(content=(Path(__file__).resolve().parents[1]/'app/static/regime_admin_panel.js').read_text())
        button=page.get_by_role('button',name=('Riconcilia dal provider' if language=='it' else 'Reconcile from provider')+' · paypal · '+local);button.wait_for()
        page.once('dialog',lambda d:d.accept());button.click()
        page.get_by_text('Ledger aggiornato; prove finanziarie ancora da verificare.' if language=='it' else 'Ledger updated; unresolved financial evidence remains.',exact=True).wait_for()
        assert resources.state(account)['credits_micro']==3_000_000 and report()['pending']==1
        documents['PP-D-123'].update(update_time='2026-10-24T03:00:00Z',dispute_outcome={'outcome_code':'RESOLVED_SELLER_FAVOUR'})
        page.once('dialog',lambda d:d.accept());button.click()
        page.get_by_text('Ledger riconciliato.' if language=='it' else 'Ledger reconciled.',exact=True).wait_for()
        assert resources.state(account)['credits_micro']==5_000_000 and report()['pending']==0
        assert 'Regime switching is not yet enabled' in page.locator('#regimeReadiness').inner_text() if language=='en' else 'Cambio di regime non ancora abilitato' in page.locator('#regimeReadiness').inner_text()
        assert not errors and all(status<400 for _,_,status in calls)
        browser.close()
