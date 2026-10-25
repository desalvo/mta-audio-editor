"""Real Chromium -> actual admin API -> persisted synthetic-kernel proof."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from app import auth, worker_cgroup_recovery as recovery
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_durable_cgroup_recovery import kernel as kernel, owned as owned, dead, economic_state  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_legal_documents import cookie


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_operator_confirmation_recovery_and_financial_hold(owned,monkeypatch,nc_browser_config,language,width):
    from app import main
    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright
    client=TestClient(main.app);client.cookies.update(cookie(1))
    before=economic_state();dead(monkeypatch);errors=[];calls=[]
    root=Path(__file__).resolve().parents[1]
    script=(root/'app/static/worker_recovery_admin.js').read_text()
    css=(root/'app/static/auth.css').read_text()+(root/'app/static/admin_controls.css').read_text()
    def serve(route):
        url=urlsplit(route.request.url)
        assert url.hostname=='mta.test'
        if url.path=='/worker-test':
            route.fulfill(content_type='text/html',body='<html lang="'+language+'"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+css+'</style><body class="settings-body"><main class="settings-grid"><section class="settings-card" id="serviceRegimePanel"></section></main></body></html>');return
        response=client.request(route.request.method,url.path+('?' + url.query if url.query else ''),headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        calls.append((route.request.method,url.path,response.status_code))
        route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config)
        page=browser.new_page(viewport={'width':width,'height':900});page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('**/*',serve);page.goto('http://mta.test/worker-test');page.add_script_tag(content=script)
        button=page.get_by_role('button',name='Verifica e arresta i processi' if language=='it' else 'Verify and stop processes')
        button.wait_for();page.once('dialog',lambda dialog:dialog.dismiss());button.click()
        assert not any(method=='POST' for method,_,_ in calls)
        page.once('dialog',lambda dialog:dialog.accept());button.click()
        page.get_by_text('Arresto verificato. Claim e riserve economiche conservati per revisione.' if language=='it' else 'Termination verified. Economic claims and reservations retained for review.',exact=True).wait_for()
        assert button.is_disabled() and not errors
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert economic_state()==before
        with auth.db() as c:assert recovery.report(c)['pending']==0
        browser.close()


def test_worker_recovery_script_is_mounted_in_actual_admin_template():
    html=(Path(__file__).resolve().parents[1]/'app/templates/admin.html').read_text()
    from bs4 import BeautifulSoup
    assert any(urlsplit(script['src']).path=='/static/worker_recovery_admin.js'
               for script in BeautifulSoup(html,'html.parser').find_all('script',src=True))
