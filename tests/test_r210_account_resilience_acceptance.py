"""Full-page voluntary NC lifecycle and simultaneous financial read failures."""
import pytest
from app import auth,ai_billing,resource_accounts as resources
from app import noncommercial_contributions as nc
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_noncommercial_collection_e2e import nc_env as nc_env,enable,receipt,overview  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_account_acceptance import configure,client,serve,assert_accessible_owner_page


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_actual_nc_owner_statement_pledge_report_receipt_csv_and_language(nc_env,monkeypatch,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright,expect
    enable(nc_env);uid=nc_env[1]
    with auth.db() as c:c.execute('UPDATE users SET language=?,limits_expanded=1 WHERE id=?',(language,uid))
    web=client(uid,monkeypatch);calls=[];errors=[]
    # Unpaid voluntary contributions cannot restrict actual work admission.
    job=ai_billing.create_job(uid,'whisper');ai_billing.finish_job(job,'done',{'cpu_seconds':1},source='worker')
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000},locale='it-IT',accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls));page.goto('https://mta.test/account#accountLimits')
        form=page.locator('[data-nc-pledge]');form.wait_for();form.locator('[name=amount]').fill('1,00' if language=='it' else '1.00')
        page.once('dialog',lambda d:d.dismiss());form.locator('button').click();assert overview(uid)['contributions']==[]
        page.once('dialog',lambda d:d.accept());form.locator('button').click();report=page.locator('[data-nc-report]');report.wait_for()
        item=overview(uid)['contributions'][0];assert item['received_cents']==0
        page.once('dialog',lambda d:d.accept());report.click();page.get_by_text('Bonifico segnalato; incasso non ancora verificato' if language=='it' else 'Transfer reported; receipt not yet verified',exact=False).wait_for()
        assert overview(uid)['contributions'][0]['received_cents']==0
        receipt(nc_env,item,amount=100);page.locator('[data-nc-refresh]').click()
        page.get_by_text('Ricevuto e verificato dall’amministratore' if language=='it' else 'Received and reviewed by administrator',exact=False).wait_for()
        assert resources.state(uid)['credits_micro']==0
        label='Incassi verificati dall’amministratore' if language=='it' else 'Receipts reviewed by administrator'
        expect(page.locator('[data-account-financial]').get_by_text(label,exact=True).locator('..').locator('span')).to_contain_text('1,00' if language=='it' else '1.00')
        nc_panel=page.locator('[data-nc-contributions]');assert ('1,00' if language=='it' else '1.00') in nc_panel.inner_text()
        other='en' if language=='it' else 'it';page.evaluate('window.MtaLocale.setChoice('+repr(other)+')')
        nc_panel.get_by_text('Received and reviewed by administrator' if other=='en' else 'Ricevuto e verificato dall’amministratore',exact=False).wait_for()
        assert ('1,00' if other=='it' else '1.00') in nc_panel.inner_text()
        with page.expect_download():page.get_by_role('button',name='Export my contribution history (CSV)' if other=='en' else 'Esporta il mio storico contributi (CSV)').click()
        with page.expect_download():page.locator('[data-nc-statement-csv]').click()
        assert overview(uid)['contributions'][0]['received_cents']==100 and not errors
        assert 'nc-bob' not in nc_panel.inner_text();assert_accessible_owner_page(page)
        with auth.db() as c:assert nc.audit(c)['verified']
        browser.close()


@pytest.mark.parametrize('path',['/account','/account/credits'])
@pytest.mark.parametrize('language',['it','en'])
def test_full_page_financial_outage_clears_stale_controls_and_explicitly_recovers(account,monkeypatch,nc_browser_config,path,language):
    from playwright.sync_api import sync_playwright
    configure(account,'active',language);web=client(account,monkeypatch);calls=[];errors=[];failed=set()
    endpoints={'/api/account/limits','/api/account/subscription','/api/account/credits','/api/account/payments','/api/account/payment-refunds'}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':390,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls,fail=failed));page.goto('https://mta.test'+path)
        page.locator('[data-owner-payments] button').first.wait_for();page.locator('[data-payment-refunds] [data-refund-content] p').first.wait_for()
        if path=='/account':page.locator('[data-cancel]').wait_for()
        failed.update(endpoints)
        if path=='/account':
            page.locator('#accountLimitsRefresh').click();page.locator('[data-resource-account] [data-refresh]').click()
            page.wait_for_function("document.querySelector('#accountLimitsContent').textContent==='' && document.querySelector('[data-resource-account] [data-content]').textContent===''")
            assert page.locator('[data-cancel],[data-storage],[data-overage]').count()==0
        else:
            page.locator('[data-credit-refresh]').click();page.wait_for_function("document.querySelector('[data-credit-content]').textContent===''")
        page.locator('[data-owner-payments] button').first.click();page.locator('[data-refund-refresh]').click()
        page.wait_for_function("document.querySelector('[data-owner-payments] [role=status]')?.textContent.includes("+repr('Storico pagamenti non disponibile' if language=='it' else 'Payment history unavailable')+")")
        assert page.locator('[data-owner-payments] article').count()==0 and page.locator('[data-refund-content] article').count()==0
        failed.clear()
        if path=='/account':page.locator('#accountLimitsRefresh').click();page.locator('[data-resource-account] [data-refresh]').click();page.locator('[data-cancel]').wait_for()
        else:page.locator('[data-credit-refresh]').click();page.locator('[data-credit-content] p').first.wait_for()
        page.locator('[data-owner-payments] button').first.click();page.locator('[data-refund-refresh]').click()
        page.locator('[data-refund-content] p').first.wait_for();assert not errors
        assert not any(method=='POST' for method,_,_ in calls)
        assert_accessible_owner_page(page);browser.close()


@pytest.mark.parametrize('language',['it','en'])
def test_nc_pledge_is_locked_across_locale_and_updates_personal_overview(nc_env,monkeypatch,nc_browser_config,language):
    from playwright.sync_api import sync_playwright,expect
    enable(nc_env);uid=nc_env[1]
    with auth.db() as c:c.execute('UPDATE users SET language=?,limits_expanded=1 WHERE id=?',(language,uid))
    web=client(uid,monkeypatch);calls=[];held=[]
    def intercept(route,url):
        if url.path=='/api/account/noncommercial-contributions' and route.request.method=='POST':held.append(route);return True
        return False
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page();page.route('**/*',serve(web,calls,intercept=intercept));page.goto('https://mta.test/account#accountLimits')
        form=page.locator('[data-nc-pledge]');form.wait_for();form.locator('[name=amount]').fill('1.00')
        page.once('dialog',lambda d:d.accept());form.locator('button').click();page.wait_for_function("document.querySelector('[data-nc-contributions]').hasAttribute('aria-busy')")
        other='en' if language=='it' else 'it';page.evaluate('window.MtaLocale.setChoice('+repr(other)+')')
        assert page.locator('[data-nc-contributions] form button:enabled').count()==0 and len(held)==1
        response=web.post('/api/account/noncommercial-contributions',content=held[0].request.post_data,headers={'Content-Type':'application/json','X-MTA-Request':'1'});assert response.status_code==200,response.text
        held[0].fulfill(status=200,content_type='application/json',body=response.content)
        page.locator('[data-nc-report]').wait_for();assert len(overview(uid)['contributions'])==1 and len(held)==1
        label='Remaining declared contributions · voluntary' if other=='en' else 'Contributi dichiarati residui · volontari'
        expect(page.locator('[data-account-financial]').get_by_text(label,exact=True).locator('..').locator('span')).to_contain_text('1.00' if other=='en' else '1,00')
        assert resources.state(uid)['credits_micro']==0;browser.close()


@pytest.mark.parametrize('language',['it','en'])
def test_nc_outage_keeps_a_keyboard_retry_and_recovers_without_fake_receipt(nc_env,monkeypatch,nc_browser_config,language):
    from playwright.sync_api import sync_playwright
    enable(nc_env);uid=nc_env[1]
    with auth.db() as c:c.execute('UPDATE users SET language=?,limits_expanded=1 WHERE id=?',(language,uid))
    web=client(uid,monkeypatch);calls=[];failed=set()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page();page.route('**/*',serve(web,calls,fail=failed));page.goto('https://mta.test/account#accountLimits')
        page.locator('[data-nc-pledge]').wait_for();failed.add('/api/account/noncommercial-contributions');page.locator('[data-nc-refresh]').click()
        page.locator('[data-nc-contributions] [role=status]').get_by_text('Ripartizione costi non disponibile' if language=='it' else 'Cost sharing unavailable',exact=False).wait_for()
        assert page.locator('[data-nc-pledge]').count()==0
        failed.clear();page.locator('[data-nc-refresh]').focus();page.keyboard.press('Enter');page.locator('[data-nc-pledge]').wait_for()
        assert overview(uid)['contributions']==[] and not any(method=='POST' for method,_,_ in calls)
        browser.close()
