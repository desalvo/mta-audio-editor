"""Owner sees durable review status without a fabricated charge or raw evidence."""
import json
from urllib.parse import urlsplit

import pytest
from app import auth
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_subscription_repayment_e2e import debt as debt  # noqa: F401
from test_r210_paypal_terminal_integrity import risk_source as risk_source  # noqa: F401
from test_r210_owner_payments import client
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401


@pytest.mark.parametrize('kind',['credits'])
@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_actual_account_displays_private_final_conflict_in_both_regimes(account,risk_source,monkeypatch,nc_browser_config,kind,language,width):
    from playwright.sync_api import sync_playwright
    local,emit=risk_source;emit('permanent',2);assert emit('released',3)['pending']
    with auth.db() as c:c.execute('UPDATE users SET language=? WHERE id=?',(language,account))
    owner=client(account,monkeypatch);errors=[];calls=[];fail={'enabled':False}
    def serve(route):
        url=urlsplit(route.request.url);assert url.hostname=='mta.test'
        if fail['enabled'] and url.path=='/api/account/payments':route.fulfill(status=503,content_type='application/json',body='{}');return
        response=owner.request(route.request.method,url.path+('?' +url.query if url.query else ''),headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        calls.append((route.request.method,url.path));route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000})
        page.on('pageerror',lambda error:errors.append(str(error)));page.route('**/*',serve);page.goto('https://mta.test/account')
        panel=page.locator('[data-owner-payments]');note='Sono registrate prove finanziarie' if language=='it' else 'Unresolved financial evidence is recorded'
        panel.get_by_text(note,exact=False).wait_for()
        assert local in panel.inner_text() and 'PP-D-FINAL' not in panel.inner_text() and 'CAPTURE111' not in panel.inner_text()
        emit('permanent',4)  # Opposite final evidence must remain unresolved.
        panel.get_by_role('button',name='Aggiorna storico' if language=='it' else 'Refresh history').click();panel.get_by_text(note,exact=False).wait_for()
        # Fixture-only regime change tests visibility; no enabled cutover is claimed.
        with auth.db() as c:c.execute("UPDATE regime_fence_state SET regime='NON_COMMERCIAL'")
        (auth.data_root()/'service-regime.json').write_text(json.dumps({'regime':'NON_COMMERCIAL','revision':0}))
        page.reload();panel.get_by_text(note,exact=False).wait_for()
        assert panel.get_by_role('button',name='Verifica esito senza incassare' if language=='it' else 'Verify status without collecting payment').count()==0
        fail['enabled']=True;panel.get_by_role('button',name='Aggiorna storico' if language=='it' else 'Refresh history').click()
        panel.get_by_text('Storico pagamenti non disponibile' if language=='it' else 'Payment history unavailable',exact=False).wait_for()
        assert panel.get_by_text(note,exact=False).count()==0
        fail['enabled']=False;panel.get_by_role('button',name='Aggiorna storico' if language=='it' else 'Refresh history').click();panel.get_by_text(note,exact=False).wait_for()
        assert not errors and page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not any(method=='POST' for method,_ in calls)
        browser.close()
