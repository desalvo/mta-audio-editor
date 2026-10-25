"""Full owner checkout, in-flight concurrency, return guards and NC receipt recovery."""
import json
from urllib.parse import urlsplit

import pytest
from app.regime_operation_fence import FenceBlocked
from app import auth,credit_purchases as shop,paypal_payments as paypal,resource_accounts as resources
from test_r210_subscriptions import account as account,plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_credit_checkout import prepare,paid_event,signed
from test_r210_subscription_repayment_e2e import debt as debt,checkout,balance  # noqa: F401
from test_r210_account_acceptance import configure,client,serve,assert_accessible_owner_page
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401


def fulfill(route,response):route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)


@pytest.mark.parametrize('kind',['stripe','paypal'])
@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_full_credit_checkout_trusted_return_and_only_verified_funding(account,provider,monkeypatch,nc_browser_config,kind,language,width):
    from playwright.sync_api import sync_playwright
    configure(account,'no_plan',language);shop_calls=prepare(account,monkeypatch)
    if kind=='stripe':paypal.settings({'enabled':False})
    else:shop.settings({'secret_key':''})  # Stripe is also configured; select the PayPal button explicitly.
    web=client(account,monkeypatch);calls=[];errors=[];current={'order':None}
    def intercept(route,url):
        if url.hostname in ('checkout.stripe.com','www.sandbox.paypal.com'):
            with auth.db() as c:
                row=c.execute('SELECT id FROM credit_purchase_orders ORDER BY created_at DESC LIMIT 1').fetchone() if kind=='stripe' else c.execute('SELECT id FROM paypal_orders ORDER BY created_at DESC LIMIT 1').fetchone()
            current['order']=row[0];assert resources.state(account)['credits_micro']==0
            route.fulfill(content_type='text/html',body='<button id="complete" onclick="location.href=\'https://mta.test/fixture-payment-complete\'">Complete simulated payment</button>');return True
        if url.path=='/fixture-payment-complete':
            if kind=='stripe':
                raw,signature=signed(paid_event(current['order']));response=web.post('/api/billing/credits/stripe-webhook',content=raw,headers={'stripe-signature':signature});assert response.status_code==200,response.text
                destination='https://mta.test/account/credits?payment=received'
            else:destination='https://mta.test/account/credits?paypal_order='+current['order']
            route.fulfill(content_type='text/html',body='<script>location.replace('+json.dumps(destination)+')</script>');return True
        return False
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls,intercept=intercept))
        page.goto('https://mta.test/account/credits?payment=received');page.locator('[data-credit-content] .plan-grid button').first.wait_for();assert resources.state(account)['credits_micro']==0
        # A return string alone never funds the actual database.
        button=page.get_by_role('button',name=('Acquista con Stripe' if language=='it' else 'Buy with Stripe') if kind=='stripe' else ('Acquista con PayPal' if language=='it' else 'Buy with PayPal')).first
        page.once('dialog',lambda d:d.dismiss());button.click();assert not any(method=='POST' for method,_,_ in calls)
        page.once('dialog',lambda d:d.accept());button.click();page.locator('#complete').wait_for()
        assert resources.state(account)['credits_micro']==0
        page.locator('#complete').click();page.wait_for_url('https://mta.test/account/credits*')
        page.wait_for_function("document.querySelector('[data-credit-content] > p')?.textContent.includes('5"+(',' if language=='it' else '.')+"00')")
        assert resources.state(account)['credits_micro']==5_000_000
        if kind=='stripe':assert len(shop_calls)==1
        else:assert sum(method=='POST' and path.endswith('/capture') for method,path,_,_ in provider[1])==1
        page.locator('[data-owner-payments]').get_by_text(current['order'],exact=False).wait_for()
        assert_accessible_owner_page(page);assert not errors
        browser.close()


@pytest.mark.parametrize('workflow',['trial','credit_stripe','credit_paypal'])
@pytest.mark.parametrize('language',['it','en'])
def test_inflight_mutation_survives_locale_change_without_second_action_or_stale_redirect(account,provider,monkeypatch,nc_browser_config,workflow,language):
    from playwright.sync_api import sync_playwright
    configure(account,'no_plan' if workflow in ('trial','credit_stripe') else 'active',language)
    if workflow=='credit_stripe':prepare(account,monkeypatch)
    web=client(account,monkeypatch);calls=[];held=[]
    target='/api/account/subscription' if workflow=='trial' else '/api/account/credits/checkout' if workflow=='credit_stripe' else '/api/account/paypal/checkout'
    def intercept(route,url):
        if route.request.method=='POST' and url.path==target:held.append(route);return True
        return False
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page();page.route('**/*',serve(web,calls,intercept=intercept))
        page.goto('https://mta.test/account#subscriptions' if workflow=='trial' else 'https://mta.test/account/credits')
        button=page.locator('[data-activate=trial]') if workflow=='trial' else page.get_by_role('button',name=('Acquista con Stripe' if language=='it' else 'Buy with Stripe') if workflow=='credit_stripe' else ('Acquista con PayPal' if language=='it' else 'Buy with PayPal')).first
        button.wait_for();page.once('dialog',lambda d:d.accept());button.click();page.wait_for_function("document.querySelector('[data-resource-account],[data-credit-shop]').getAttribute('aria-busy')==='true'")
        other='en' if language=='it' else 'it';page.evaluate('window.MtaLocale.setChoice('+repr(other)+')')
        panel=page.locator('[data-resource-account]' if workflow=='trial' else '[data-credit-shop]')
        assert panel.locator('[data-activate]:enabled,[data-storage]:enabled,[data-cancel]:enabled,.plan-grid button:enabled').count()==0
        assert len(held)==1
        request=held[0].request;response=web.request(request.method,urlsplit(request.url).path,content=request.post_data,headers={'X-MTA-Request':'1','Content-Type':'application/json'});assert response.status_code==200,response.text
        fulfill(held[0],response)
        page.wait_for_function("!document.querySelector('[data-resource-account],[data-credit-shop]').hasAttribute('aria-busy')")
        if workflow=='trial':page.locator('[data-cancel]').wait_for();assert resources.state(account)['subscription']=='trial'
        else:
            page.locator('[data-owner-payments]').get_by_role('button',name='Resume existing checkout' if other=='en' else 'Riprendi checkout esistente').wait_for()
            assert panel.locator('.plan-grid button').count()==0 and page.url.startswith('https://mta.test/account/credits')
        assert len(held)==1
        browser.close()


def switch_nc():
    (auth.data_root()/'service-regime.json').write_text(json.dumps({'regime':'NON_COMMERCIAL','revision':0}))
    with auth.db() as c:c.execute("UPDATE regime_fence_state SET regime='NON_COMMERCIAL'")


def test_pending_subscription_fee_is_private_and_never_offers_a_second_checkout(account,provider,monkeypatch):
    plan(account,price_micro=5_000_000);period=resources.state(account)['period']['start']
    order=paypal.checkout(account,{'kind':'subscription','period_start':period,'request_id':'acceptance-pending-fee'})
    web=client(account,monkeypatch);data=web.get('/api/account/subscription').json()
    assert data['pending_subscription_periods']==[period]
    from test_r210_legal_documents import cookie
    web.cookies.update(cookie(auth.find_user('admin')['id']))
    assert web.get('/api/account/subscription').json()['pending_subscription_periods']==[]
    assert order['order_id'] not in json.dumps(web.get('/api/account/subscription').json())


def test_noncommercial_blocks_capture_and_foreign_epoch_but_original_epoch_readback_settles(account,provider,debt,monkeypatch):
    local=checkout(account)['order_id'];switch_nc();before=len(provider[1])
    with pytest.raises(ValueError):paypal.capture(account,local)
    assert not any(method=='POST' and path.endswith('/capture') for method,path,_,_ in provider[1][before:])
    with auth.db() as c:assert c.execute('SELECT status FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]=='pending'
    # Simulate an independently completed original commercial payment. Local
    # authenticated readback remains allowed; it never starts another capture.
    with auth.db() as c:pid=c.execute('SELECT provider_order FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]
    paypal._api({},'POST','/v2/checkout/orders/'+pid+'/capture')
    before=len(provider[1])
    with pytest.raises(FenceBlocked):paypal.capture(account,local)
    assert all(method=='GET' for method,_,_,_ in provider[1][before:]) and balance(account)['due_micro']==3_000_000
    # Only restoration of the exact original admission epoch permits settlement.
    (auth.data_root()/'service-regime.json').write_text(json.dumps({'regime':'COMMERCIAL','revision':0}))
    with auth.db() as c:c.execute("UPDATE regime_fence_state SET regime='COMMERCIAL'")
    before=len(provider[1]);assert paypal.capture(account,local)['status']=='paid'
    assert all(method=='GET' for method,_,_,_ in provider[1][before:]) and balance(account)['due_micro']==0


@pytest.mark.parametrize('path',['/account','/account/credits'])
@pytest.mark.parametrize('pending_kind',['repayment','credits'])
def test_noncommercial_owner_return_url_never_attempts_automatic_capture(account,provider,debt,monkeypatch,nc_browser_config,path,pending_kind):
    from playwright.sync_api import sync_playwright
    local=checkout(account)['order_id'] if pending_kind=='repayment' else paypal.checkout(account,{'kind':'credits','amount_cents':500,'request_id':'nc-return-credits-123'})['order_id'];switch_nc();web=client(account,monkeypatch);calls=[];before=len(provider[1])
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page();page.route('**/*',serve(web,calls))
        page.goto('https://mta.test'+path+'?paypal_order='+local);page.locator('[data-owner-payments]').get_by_text(local,exact=False).wait_for()
        assert not any(method=='POST' and url.endswith('/capture') for method,url,_ in calls)
        assert len(provider[1])==before
        if path.endswith('/credits'):assert 'Payments unavailable' in page.locator('[data-credit-shop]').inner_text()
        assert resources.state(account)['credits_micro']==0 and balance(account)['due_micro']==3_000_000
        browser.close()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_full_owner_recovers_approved_credit_payment_without_url_or_new_checkout(account,provider,monkeypatch,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    from test_r210_checkout_reference_recovery import unknown_paypal
    from app import checkout_reference_recovery
    local,ref,_=unknown_paypal(account,provider,monkeypatch)
    assert checkout_reference_recovery.recover('paypal',local,ref)['reference_confirmed']
    with auth.db() as c:c.execute('UPDATE users SET language=?,limits_expanded=1 WHERE id=?',(language,account))
    web=client(account,monkeypatch);calls=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls));page.goto('https://mta.test/account')
        page.get_by_role('link',name='Completa questo pagamento esistente nella pagina crediti' if language=='it' else 'Complete this existing payment on the credits page').click()
        button=page.locator('[data-existing-payment-capture]');button.wait_for();before=len(provider[1])
        page.once('dialog',lambda d:d.dismiss());button.click();assert resources.state(account)['credits_micro']==0 and len(provider[1])==before
        page.once('dialog',lambda d:d.accept());button.click();page.get_by_text('Pagamento verificato' if language=='it' else 'Payment verified',exact=True).wait_for()
        assert resources.state(account)['credits_micro']==5_000_000 and len(provider[0])==1
        assert sum(method=='POST' and path.endswith('/capture') for method,path,_,_ in provider[1][before:])==1
        assert page.locator('[data-existing-payment-capture]').count()==0 and not errors
        assert_accessible_owner_page(page);browser.close()
