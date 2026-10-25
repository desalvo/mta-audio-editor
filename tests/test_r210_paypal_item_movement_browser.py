"""Actual owner pages and admin/API exercise exact partial risk and review."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from app import auth,resource_accounts as resources
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_account_acceptance import client,serve,assert_accessible_owner_page
from test_r210_paypal_item_movements import partial,movements
from test_r210_paypal_dispute_history import report


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
@pytest.mark.parametrize('path',['/account','/account/credits'])
def test_actual_owner_page_exact_partial_multicapture_then_supported_release(account,provider,monkeypatch,nc_browser_config,language,width,path):
    from playwright.sync_api import sync_playwright
    _,_,docs,_,_=partial(account,provider,monkeypatch,paid=True)
    with auth.db() as c:c.execute('UPDATE users SET language=?,limits_expanded=1 WHERE id=?',(language,account))
    web=client(account,monkeypatch);calls=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls));page.goto('https://mta.test'+path)
        panel=page.locator('[data-owner-payments]');button=panel.get_by_role('button',name='Verifica esito senza incassare' if language=='it' else 'Verify status without collecting payment');button.wait_for()
        page.once('dialog',lambda d:d.accept());button.click()
        panel.get_by_text('Fondi del pagamento trattenuti o stornati:' if language=='it' else 'Payment funds held or reversed:',exact=False).wait_for()
        assert resources.state(account)['credits_micro']==2_000_000 and report()['positions'][0]['held_minor']==300
        assert all(x not in panel.inner_text() for x in ('ITEM-A','ITEM-C','private buyer','CAPTURE111','PP-D-123'))
        docs['PP-D-123'].update(status='RESOLVED',update_time='2026-10-24T04:00:00Z',dispute_outcome={'outcome_code':'RESOLVED_SELLER_FAVOUR'})
        page.once('dialog',lambda d:d.accept());button.click()
        page.wait_for_function("!document.querySelector('[data-owner-payments]').textContent.includes("+repr('Fondi del pagamento' if language=='it' else 'Payment funds held')+") && !document.querySelector('[data-owner-payments] button').disabled")
        assert resources.state(account)['credits_micro']==5_000_000 and report()['pending']==0
        assert_accessible_owner_page(page);assert not errors and all(code<400 for _,_,code in calls)
        assert not any('/capture' in url or url.endswith('/checkout') for _,url,_ in calls)
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_admin_canonical_movement_observations_have_no_settlement_action(account,provider,monkeypatch,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    local,_,docs,_,_=partial(account,provider,monkeypatch,paid=True)
    d=docs['PP-D-123'];d.update(status='RESOLVED',dispute_outcome={'outcome_code':'RESOLVED_WITH_PAYOUT'},**movements(reason='DISPUTE_FEE',value='90071992547409.93',direction='CREDIT'))
    web=client(auth.find_user('admin')['id'],monkeypatch);calls=[];errors=[];fail={'on':False}
    def route(route):
        url=urlsplit(route.request.url);assert url.hostname=='mta.test'
        if url.path=='/movement-admin':
            route.fulfill(content_type='text/html',body='<html lang="'+language+'"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{overflow-wrap:anywhere}button{max-width:100%}table{font-size:.8em}</style><main id="serviceRegimePanel"></main></html>');return
        return serve(web,calls,fail={'/api/admin/service-regime/payment-ledger'} if fail['on'] else None)(route)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',route);page.goto('https://mta.test/movement-admin')
        page.add_script_tag(content=(Path(__file__).resolve().parents[1]/'app/static/regime_admin_panel.js').read_text())
        button=page.get_by_role('button',name=('Riconcilia dal provider' if language=='it' else 'Reconcile from provider')+' · paypal · '+local);button.wait_for()
        page.once('dialog',lambda dialog:dialog.accept());button.click()
        panel=page.locator('[data-movement-review]');panel.wait_for();panel.locator('summary').click()
        assert 'DISPUTE_FEE' in panel.inner_text() and '90.071.992.547.409,93' in panel.inner_text() if language=='it' else 'DISPUTE_FEE' in panel.inner_text() and '90,071,992,547,409.93' in panel.inner_text()
        assert 'NEVER EXPOSE' not in panel.inner_text() and 'private buyer' not in panel.inner_text()
        assert panel.get_by_role('button').count()==0
        assert resources.state(account)['credits_micro']==2_000_000 and report()['pending']==2
        region=panel.get_by_role('region',name='Osservazioni dei movimenti PayPal' if language=='it' else 'PayPal movement observations');region.focus();assert region.evaluate('e=>document.activeElement===e')
        if region.evaluate('e=>e.scrollWidth>e.clientWidth+2'):
            page.keyboard.press('ArrowRight');page.wait_for_function('e=>e.scrollLeft>0',arg=region.element_handle())
        fail['on']=True;page.locator('#regimeRefresh').click();page.wait_for_function("!document.querySelector('#regimeFinance').textContent")
        assert panel.count()==0
        fail['on']=False;page.locator('#regimeRefresh').click();panel.wait_for()
        assert resources.state(account)['credits_micro']==2_000_000
        assert ('Regime switching is not yet enabled' if language=='en' else 'Cambio di regime non ancora abilitato') in page.locator('#regimeReadiness').inner_text()
        assert not errors;browser.close()
