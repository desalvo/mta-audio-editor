"""Real Chromium DOM/event regression for the subscription operator interface."""
import json
from pathlib import Path

import pytest

playwright=pytest.importorskip('playwright.sync_api')
ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("width",[1280,480])
def test_incremental_user_picker_amendment_and_paypal_configuration(width):
    cfg={'enabled':True,'credits_enabled':True,'self_service':True,'credit_value_micro':100000,'credit_denominations':'[500,1000]','plans':[{'code':'day','cpu_seconds':14400,'gpu_seconds':14400,'storage_bytes':5*1024**3,'price_micro':0}],'tariffs':{k:{'micro_per_unit':v} for k,v in [('cpu_seconds',1),('gpu_seconds',10),('disk_gb_hours',20)]}}
    state={'subscription':'day','promo':'','funded':True,'period':{'start':100,'end':86500},'credits_micro':1000000,'credits_enabled':True,'credit_value_micro':100000,'limits':{'cpu_seconds':14400,'gpu_seconds':14400,'storage_bytes':5*1024**3},'used':{'cpu_seconds':3600,'gpu_seconds':1800,'storage_bytes':1000},'transactions':{'credits':[],'overages':[]},'history':[],'trial_available':True,'policy':{'access_required':False,'subscriptions_allowed':True,'credit_billing':True}}
    requests=[]
    with playwright.sync_playwright() as p:
        try:browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        except playwright.Error as exc:pytest.skip('Chromium unavailable: '+str(exc)[:160])
        page=browser.new_page(viewport={'width':width,'height':900});errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        def serve(route):
            path=route.request.url.split('https://mta.test',1)[-1]
            if path=='/':route.fulfill(content_type='text/html',body='<style>'+ (ROOT/'app/static/auth.css').read_text()+(ROOT/'app/static/admin_controls.css').read_text()+(ROOT/'app/static/subscriptions.css').read_text()+'</style><section class="resource-panel" data-resource-admin></section>');return
            if path.startswith('/api/admin/subscription-users?'):
                data=[{'id':2,'username':'alessandro','email':'alex@example.test','display_name':'Alessandro'}]
            elif path=='/api/service-regime':data={'regime':'COMMERCIAL'}
            elif path=='/api/admin/subscriptions':data=cfg
            elif path=='/api/admin/subscriptions/users/2':data=state
            elif path=='/api/admin/paypal':
                if route.request.method=='PUT':requests.append((path,route.request.post_data_json))
                data={'enabled':False,'environment':'sandbox','configured':False}
            elif path=='/api/admin/subscriptions/users/2/limits':
                body=route.request.post_data_json;requests.append((path,body));state['limits']=body['limits'];data=state
            else:raise AssertionError(path)
            route.fulfill(content_type='application/json',body=json.dumps(data))
        page.route('https://mta.test/**',serve);page.goto('https://mta.test/')
        page.add_script_tag(content='window.MtaLocale={language:"en"};'+(ROOT/'app/static/subscriptions.js').read_text())
        page.wait_for_selector('[data-search]')
        assert page.locator('[data-user-results]').is_hidden()
        assert page.locator('select[data-user]').count()==0
        page.locator('[data-search]').fill('alex')
        option=page.get_by_role('option',name='Alessandro · alessandro · alex@example.test');option.wait_for()
        option.click();page.wait_for_selector('[data-amend]',state='attached')
        assert page.locator('[data-selected-user]').inner_text().startswith('Alessandro')
        assert page.locator('[data-user-results]').is_hidden()
        assert page.locator('[data-credit-billing]').count()==0
        assert not page.locator('[data-assign]').evaluate('(el)=>el.closest("details").open')
        page.locator('[data-promo-shortcut]').click()
        assert page.locator('[data-assign]').evaluate('(el)=>el.closest("details").open')
        assert page.locator('[data-assign-plan]').input_value()=='week'
        page.locator('[data-amend]').evaluate('(el)=>el.closest("details").open=true')
        page.locator('[data-field=amend-cpu_seconds]').fill('6')
        page.locator('[data-free=cpu_seconds]').select_option('free')
        page.locator('[data-field=amend-reason]').fill('Promotion extension')
        page.locator('[data-amend]').click();page.wait_for_timeout(100)
        assert requests[0][1]['limits']['cpu_seconds']==21600
        assert requests[0][1]['free_increases']['cpu_seconds'] is True
        page.locator('[data-paypal-save]').evaluate('(el)=>el.closest("details").open=true')
        assert page.locator('[data-paypal-enabled]').bounding_box()['width']<=24
        page.locator('[data-paypal-id]').fill('example-client')
        page.locator('[data-paypal-secret]').fill('example-secret')
        page.locator('[data-paypal-webhook]').fill('example-webhook')
        page.locator('[data-paypal-save]').click();page.wait_for_timeout(100)
        assert requests[-1][1]['client_secret']=='example-secret'
        assert page.locator('[data-paypal-secret]').input_value()==''
        assert not errors,errors
        browser.close()
