"""Actual token report read failures and reversed responses never become fresh zero/history."""
import pytest
from app import ai_billing
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_account_acceptance import configure,client,serve


@pytest.mark.parametrize('language',['it','en'])
def test_actual_resource_report_outage_and_late_prior_interval(account,monkeypatch,nc_browser_config,language):
    from playwright.sync_api import sync_playwright,expect
    configure(account,'active',language)
    job=ai_billing.create_job(account,'whisper');ai_billing.finish_job(job,'done',{'cpu_seconds':1},source='worker')
    web=client(account,monkeypatch);calls=[];failed=set();held=[];delay={'enabled':False}
    def intercept(route,url):
        if delay['enabled'] and url.path=='/api/account/ai-resources':
            delay['enabled']=False;held.append(route);return True
        return False
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page();page.route('**/*',serve(web,calls,fail=failed,intercept=intercept));page.goto('https://mta.test/account')
        page.locator('.limits-token-detail > summary').click();panel=page.locator('.ai-resource-panel')
        expect(panel.locator('[data-totals]')).to_contain_text('1 job')
        failed.add('/api/account/ai-resources');panel.locator('[data-refresh]').click()
        panel.get_by_text('Report non disponibile' if language=='it' else 'Report unavailable',exact=False).wait_for()
        assert panel.locator('[data-totals]').inner_text()==''
        assert '1 job' not in panel.locator('[data-rows]').inner_text()
        failed.clear();panel.locator('[data-refresh]').focus();page.keyboard.press('Enter');expect(panel.locator('[data-totals]')).to_contain_text('1 job')
        assert 'unavailable' not in panel.locator('[data-status]').inner_text().lower() and 'non disponibile' not in panel.locator('[data-status]').inner_text().lower()
        # Capture a genuine current-period response, then request an older empty
        # interval before releasing it. Only the latest chosen interval can render.
        delay['enabled']=True;panel.locator('[data-refresh]').click();page.wait_for_function("document.querySelector('.ai-resource-panel [data-totals]').textContent.includes("+repr('Caricamento' if language=='it' else 'Loading')+")")
        assert len(held)==1
        original=web.get(held[0].request.url.replace('https://mta.test',''));assert original.status_code==200 and original.json()['jobs']==1
        panel.locator('[data-start]').fill('2000-01-01');panel.locator('[data-end]').fill('2000-01-02');panel.locator('[data-refresh]').click()
        expect(panel.locator('[data-totals]')).to_contain_text('0 job')
        held[0].fulfill(status=200,content_type='application/json',body=original.content)
        page.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        assert panel.locator('[data-totals]').inner_text().startswith('0 job')
        assert not any(method=='POST' for method,_,_ in calls)
        browser.close()
