"""Shipped refund UI -> real authenticated API -> actual local financial ledger.

Only payment-provider I/O is simulated. This isolated component harness is not
full administration/account or installed-native accessibility acceptance.
"""
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from app import operator_refunds as refunds, resource_accounts
from test_r210_operator_refunds import stripe_env as stripe_env, paypal_env as paypal_env, actor, create  # noqa: F401
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_legal_documents import cookie
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401


def clients(account,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    admin=TestClient(main.app);admin.cookies.update(cookie(actor()))
    owner=TestClient(main.app);owner.cookies.update(cookie(account))
    return admin,owner


def server(client,language,admin,calls,errors):
    root=Path(__file__).resolve().parents[1]
    css=(root/'app/static/operator_refunds.css').read_text()+(root/'app/static/auth.css').read_text()
    def serve(route):
        url=urlsplit(route.request.url);assert url.hostname=='mta.test'
        if url.path=='/refund-test':
            route.fulfill(content_type='text/html',body=f'<html lang="{language}"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style><body class="settings-body"><main class="settings-grid"><section class="settings-card" data-payment-refunds="'+('admin' if admin else 'owner')+'"></section></main></body></html>');return
        result=client.request(route.request.method,url.path+('?' +url.query if url.query else ''),headers={'Content-Type':'application/json','X-MTA-Request':'1'},content=route.request.post_data)
        calls.append((route.request.method,url.path,result.status_code))
        if result.status_code>=500:errors.append(result.text)
        route.fulfill(status=result.status_code,content_type='application/json',body=result.content)
    return serve


@pytest.mark.parametrize('environment',['stripe_env','paypal_env'])
@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_admin_prepare_confirm_execute_cancel_and_private_owner_view(request,account,monkeypatch,nc_browser_config,environment,language,width):
    from playwright.sync_api import sync_playwright
    env=request.getfixturevalue(environment);admin,owner=clients(account,monkeypatch)
    from app import payment_reconcile_service
    payment_reconcile_service.reconcile_checkout('stripe' if environment=='stripe_env' else 'paypal',env['order'])
    calls=[];errors=[];root=Path(__file__).resolve().parents[1];script=(root/'app/static/operator_refunds.js').read_text()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':900})
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',server(admin,language,True,calls,errors))
        page.goto('https://mta.test/refund-test');page.add_script_tag(content=script)
        form=page.locator('[data-refund-prepare]');form.wait_for();form.locator('[name=amount]').fill('2,00' if language=='it' else '2.00')
        reason='<img src=x onerror=alert(1)> customer refund';form.locator('[name=reason]').fill(reason)
        page.once('dialog',lambda d:d.dismiss());form.locator('button').click();assert refunds.overview()['items']==[] and not env['posts']
        page.once('dialog',lambda d:d.accept());form.locator('button').click()
        article=page.locator('[data-refund-state=prepared]');article.wait_for();assert not env['posts']
        assert reason in article.inner_text() and article.locator('img').count()==0
        page.once('dialog',lambda d:d.dismiss());article.locator('[data-refund-execute]').click();assert not env['posts']
        page.once('dialog',lambda d:d.accept());article.locator('[data-refund-execute]').click()
        page.locator('[data-refund-state=settled]').wait_for();assert len(env['posts'])==1
        assert resource_accounts.state(account)['credits_micro']==3_000_000
        assert page.locator('[data-refund-execute]').count()==0
        # A second preparation can be cancelled before provider dispatch.
        form=page.locator('[data-refund-prepare]');form.locator('[name=amount]').fill('0.50');form.locator('[name=reason]').fill('Cancelled operator draft')
        page.once('dialog',lambda d:d.accept());form.locator('button').click();article=page.locator('[data-refund-state=prepared]');article.wait_for()
        page.once('dialog',lambda d:d.accept());article.locator('[data-refund-cancel]').click();page.locator('[data-refund-state=cancelled]').wait_for()
        assert len(env['posts'])==1
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        owner_page=browser.new_page(viewport={'width':width,'height':900});owner_page.on('pageerror',lambda e:errors.append(str(e)))
        owner_page.route('**/*',server(owner,language,False,calls,errors));owner_page.goto('https://mta.test/refund-test');owner_page.add_script_tag(content=script)
        owner_page.locator('[data-refund-state=settled]').wait_for();assert env['order'] in owner_page.locator('[data-refund-content]').inner_text()
        assert reason not in owner_page.locator('body').inner_text();assert owner_page.locator('form').count()==0
        assert owner_page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        assert not errors and all(code==200 for _,_,code in calls)
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
def test_uncertain_browser_only_recovers_existing_reference(stripe_env,account,monkeypatch,nc_browser_config,language):
    from playwright.sync_api import sync_playwright
    item=create(stripe_env);stripe_env['timeout']=True;refunds.execute(actor(),item['id'],0)
    admin,_=clients(account,monkeypatch);calls=[];errors=[];root=Path(__file__).resolve().parents[1]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page()
        page.route('**/*',server(admin,language,True,calls,errors));page.goto('https://mta.test/refund-test');page.add_script_tag(content=(root/'app/static/operator_refunds.js').read_text())
        form=page.locator('[data-refund-verify]');form.wait_for();assert page.locator('[data-refund-execute]').count()==0 and page.locator('[data-refund-cancel]').count()==0
        form.locator('[name=reference]').fill(next(iter(stripe_env['refunds'])));form.locator('button').click()
        page.locator('[data-refund-state=settled]').wait_for();assert len(stripe_env['posts'])==1 and not errors
        assert any('/verify' in path for _,path,_ in calls)
        assert not any('/execute' in path for _,path,_ in calls)
        browser.close()


def test_auth_csrf_exact_shapes_private_pagination_and_unknown_action(stripe_env,account,monkeypatch):
    from app import main
    admin,owner=clients(account,monkeypatch);anonymous=TestClient(main.app);headers={'X-MTA-Request':'1'}
    assert anonymous.get('/api/admin/payment-refunds').status_code==401
    assert anonymous.get('/api/account/payment-refunds').status_code==401
    assert owner.get('/api/admin/payment-refunds').status_code==403
    assert owner.post('/api/admin/payment-refunds',headers=headers,json={}).status_code==403
    assert admin.post('/api/admin/payment-refunds',json={}).status_code==403
    assert admin.post('/api/admin/payment-refunds',headers=headers,json={'provider':'stripe'}).status_code==422
    item=create(stripe_env)
    assert admin.post('/api/admin/payment-refunds/'+item['id']+'/unknown',headers=headers,json={'expected_revision':0}).status_code==404
    for action in ('execute','verify','cancel'):
        endpoint='/api/admin/payment-refunds/'+item['id']+'/'+action
        assert admin.post(endpoint,headers=headers,json={'expected_revision':0,'amount_cents':1}).status_code==422
        assert owner.post(endpoint,headers=headers,json={'expected_revision':0}).status_code==403
        assert admin.post(endpoint,headers=headers,json={'expected_revision':None}).status_code==422
    assert admin.get('/api/admin/payment-refunds?limit=0').status_code==422
    assert owner.get('/api/account/payment-refunds?offset=-1').status_code==422
    assert len(owner.get('/api/account/payment-refunds').json()['items'])==1
    admin_owner=admin.get('/api/account/payment-refunds').json();assert admin_owner['items']==[]
    assert not stripe_env['posts']


def test_all_actual_owner_admin_templates_load_the_shared_refund_ui():
    root=Path(__file__).resolve().parents[1]
    for name,mode in [('admin.html','admin'),('account.html','owner'),('credits.html','owner')]:
        template=(root/'app/templates'/name).read_text()
        assert f'data-payment-refunds="{mode}"' in template
        assert '/static/operator_refunds.js?v=r210-owner-account-acceptance' in template
        assert '/static/operator_refunds.css?v=r210-refund-workflow' in template
