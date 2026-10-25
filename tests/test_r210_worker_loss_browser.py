from pathlib import Path
from urllib.parse import urlsplit

import pytest
from app import auth
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_durable_cgroup_recovery import kernel as kernel,owned as owned  # noqa: F401
from test_r210_worker_loss_resolution import stopped as stopped  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_legal_documents import cookie
from test_r210_noncommercial_collection_e2e import nc_env as nc_env  # noqa: F401


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_explicit_operator_loss_and_private_owner_history(stopped,account,nc_browser_config,language,width):
    from app import main
    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright
    client=TestClient(main.app);client.cookies.update(cookie(1));calls=[];errors=[]
    root=Path(__file__).resolve().parents[1]
    css=(root/'app/static/auth.css').read_text()+(root/'app/static/admin_controls.css').read_text()
    def serve(route):
        url=urlsplit(route.request.url);assert url.hostname=='mta.test'
        if url.path in ('/loss-test','/owner-test'):
            content='<section class="settings-card" id="serviceRegimePanel"></section>' if url.path=='/loss-test' else '<section class="settings-card" data-worker-loss-history hidden></section>'
            route.fulfill(content_type='text/html',body='<html lang="'+language+'"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+css+'</style><body class="settings-body"><main class="settings-grid">'+content+'</main></body></html>');return
        response=client.request(route.request.method,url.path+('?' +url.query if url.query else ''),headers={'X-MTA-Request':'1','Content-Type':'application/json'},content=route.request.post_data)
        calls.append((route.request.method,url.path,response.status_code))
        route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':900})
        page.on('pageerror',lambda error:errors.append(str(error)));page.route('**/*',serve)
        page.goto('http://mta.test/loss-test');page.add_script_tag(content=(root/'app/static/worker_loss_admin.js').read_text())
        review=page.get_by_role('button',name='Esamina perdita a carico del gestore' if language=='it' else 'Review operator-funded loss');review.click()
        form=page.locator('#workerLossPanel form');form.wait_for()
        reason='Verified operator loss. <img src=x onerror=alert(1)> Unknown consumption remains unknown.'
        form.locator('[name=reason]').fill(reason);form.locator('[name=evidence_sha256]').fill('a'*64)
        form.locator('button').click();assert not any(method=='POST' for method,_,_ in calls)
        for name in ('confirm_operator_loss','confirm_no_customer_charge','confirm_no_reallocation'):form.locator('[name='+name+']').check()
        page.once('dialog',lambda dialog:dialog.dismiss());form.locator('button').click()
        assert not any(method=='POST' for method,_,_ in calls)
        page.once('dialog',lambda dialog:dialog.accept());form.locator('button').click()
        page.get_by_text('Approvato. Riserve liberate; nessun addebito; consumi sconosciuti conservati.' if language=='it' else 'Approved. Reservations released; no charge; unknown consumption retained.',exact=True).wait_for()
        assert not errors and page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        with auth.db() as c:
            assert c.execute('SELECT status FROM ai_compute_jobs').fetchone()[0]=='failed'
            assert c.execute('SELECT charge_micro FROM resource_job_contracts').fetchone()[0]==0
        client.cookies.update(cookie(account));page.goto('http://mta.test/owner-test')
        page.add_script_tag(content=(root/'app/static/worker_loss_history.js').read_text())
        page.get_by_text('Job interrotti senza addebiti' if language=='it' else 'Interrupted jobs without charges',exact=True).wait_for()
        assert reason in page.locator('[data-worker-loss-history]').inner_text()
        assert page.locator('[data-worker-loss-history] img').count()==0
        assert not errors and page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        browser.close()


def test_actual_templates_mount_both_operator_and_owner_flows():
    root=Path(__file__).resolve().parents[1]
    from bs4 import BeautifulSoup
    scripts=BeautifulSoup((root/'app/templates/admin.html').read_text(),'html.parser').find_all('script',src=True)
    assert any(urlsplit(script['src']).path=='/static/worker_loss_admin.js' for script in scripts)
    assert 'data-worker-loss-history' in (root/'app/templates/account.html').read_text()
    assert '/static/worker_loss_history.js?v=r210-worker-loss' in (root/'app/templates/account.html').read_text()


def test_nc_period_form_cannot_reallocate_operator_losses_without_cost_review(nc_env,kernel,nc_browser_config,monkeypatch):
    from app import main,ai_billing,worker_cgroup_recovery as processes,worker_loss_resolution as losses
    from app.regime_worker_claims import claim
    from test_r210_durable_cgroup_recovery import dead
    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright
    job=ai_billing.create_job(nc_env[1],'whisper',started_at=400)
    credentials={'worker_id':'nc-crash-owner','claim_token':'fixture-nc-token'}
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');claim(c,job,worker_id=credentials['worker_id'],token=credentials['claim_token'])
    scope=processes.register(kernel,job,credentials);processes.owner_quiescent(scope);dead(monkeypatch)
    with auth.db() as c:plan=losses.preview(c,job,nc_env[0])
    losses.resolve(job,nc_env[0],{'request_id':'nc-operator-loss-browser','expected_sha256':plan['expected_sha256'],
      'reason':'Documented NC loss absorbed by the operator without allocating it to other users.',
      'evidence_sha256':'b'*64,'confirm_operator_loss':True,'confirm_no_customer_charge':True,'confirm_no_reallocation':True})
    measured=ai_billing.create_job(nc_env[2],'whisper',started_at=450)
    ai_billing.finish_job(measured,'done',{'cpu_seconds':1},source='worker',finished_at=452)
    client=TestClient(main.app);client.cookies.update(cookie(nc_env[0]));root=Path(__file__).resolve().parents[1]
    from test_r210_noncommercial_collection_browser import page_server
    calls=[];errors=[]
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':390,'height':900},timezone_id='UTC')
        page.route('**/*',page_server(client,'it',True,calls,errors));page.goto('http://mta.test/nc-test')
        page.add_script_tag(content=(root/'app/static/noncommercial_contributions.js').read_text())
        form=page.locator('[data-nc-close]');form.wait_for()
        form.locator('[name=start]').fill('1970-01-01T00:05');form.locator('[name=end]').fill('1970-01-01T00:08:20')
        form.locator('[name=cost]').fill('1.00')
        page.once('dialog',lambda dialog:dialog.accept());form.locator('button').click()
        page.get_by_text('Period cannot be safely closed',exact=False).wait_for()
        with auth.db() as c:assert c.execute('SELECT count(*) FROM nc_period_statements').fetchone()[0]==1
        # The rejection refreshes and replaces the form. Wait for the new form
        # before editing it; otherwise refresh can discard the second submit.
        page.wait_for_function("document.querySelectorAll('[data-nc-close] button:not([disabled])').length===1")
        form.locator('[name=start]').fill('1970-01-01T00:05');form.locator('[name=end]').fill('1970-01-01T00:08:20')
        form.locator('[name=cost]').fill('1.00')
        form.locator('[name=excludeLosses]').check();page.once('dialog',lambda dialog:dialog.accept());form.locator('button').click()
        try:
            page.wait_for_function("document.querySelectorAll('[data-nc-statement-csv]').length===2",timeout=5000)
        except Exception:
            raise AssertionError({'body':page.locator('body').inner_text(),'calls':calls,'errors':errors}) from None
        with auth.db() as c:
            import json
            record=json.loads(c.execute('SELECT statement_json FROM nc_period_statements WHERE period_start=300').fetchone()[0])
            assert record['operator_cost_exclusion_confirmed'] and record['contribution_cents']=={str(nc_env[2]):100}
            assert record['operator_losses'][0]['job_id']==job
        assert not errors
        browser.close()
