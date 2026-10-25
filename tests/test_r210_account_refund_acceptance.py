"""Real completed-refund accounting on both complete owner pages, privately."""
import json
import pytest
from app import auth,operator_refunds as refunds,resource_accounts
from test_r210_operator_refunds import stripe_env as stripe_env,actor,create  # noqa: F401
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_account_acceptance import client,serve,assert_accessible_owner_page


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_actual_account_refund_amount_wallet_privacy_outage_and_nc_history(stripe_env,account,monkeypatch,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    item=create(stripe_env);assert refunds.execute(actor(),item['id'],0)['state']=='settled'
    assert resource_accounts.state(account)['credits_micro']==3_000_000
    with auth.db() as c:c.execute('UPDATE users SET language=?,limits_expanded=1 WHERE id=?',(language,account))
    web=client(account,monkeypatch);calls=[];errors=[];failed=set()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)));page.route('**/*',serve(web,calls,fail=failed))
        for path in ('/account','/account/credits'):
            page.goto('https://mta.test'+path);panel=page.locator('[data-payment-refunds]');panel.locator('[data-refund-state=settled]').wait_for()
            assert ('2,00' if language=='it' else '2.00') in panel.inner_text()
            assert not any(word in panel.inner_text() for word in ('pi_test','re_operator','Customer requested','actor_id'))
            assert panel.locator('form').count()==0 and not errors
            if path=='/account':
                page.locator('[data-account-financial]').wait_for();assert ('3,00' if language=='it' else '3.00') in page.locator('[data-account-financial]').inner_text()
            else:
                page.locator('[data-credit-content] p').first.wait_for();assert ('3,00' if language=='it' else '3.00') in page.locator('[data-credit-content] p').first.inner_text()
            failed.add('/api/account/payment-refunds');panel.locator('[data-refund-refresh]').click()
            panel.get_by_text('Operazione non confermata' if language=='it' else 'Operation not confirmed',exact=False).wait_for();assert panel.locator('article').count()==0
            failed.clear();panel.locator('[data-refund-refresh]').focus();page.keyboard.press('Enter');panel.locator('[data-refund-state=settled]').wait_for()
            assert_accessible_owner_page(page)
        # A fixture-only historical view, not an enabled administrative cutover.
        (auth.data_root()/'service-regime.json').write_text(json.dumps({'regime':'NON_COMMERCIAL','revision':0}))
        with auth.db() as c:c.execute("UPDATE regime_fence_state SET regime='NON_COMMERCIAL'")
        page.reload();page.locator('[data-refund-state=settled]').wait_for()
        assert ('Saldo storico:' if language=='it' else 'Historical balance:') in page.locator('[data-credit-content]').inner_text()
        assert page.locator('[data-credit-content] .plan-grid button').count()==0
        assert resource_accounts.state(account)['credits_micro']==3_000_000 and len(stripe_env['posts'])==1
        browser.close()
