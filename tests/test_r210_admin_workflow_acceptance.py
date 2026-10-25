"""Actual keyboard mutations and read failures of the administration, isolated locally."""
import os

import pytest
from app import auth, storage, ai_access, account_lifecycle
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401
from test_r210_admin_accessibility import setup, scan
from test_r210_account_acceptance import serve


def start(account, monkeypatch, config, language, width, fail=None):
    from playwright.sync_api import sync_playwright
    web=setup(account,monkeypatch,'commercial',language)
    manager=sync_playwright().start();browser=manager.chromium.launch(**config)
    page=browser.new_page(viewport={'width':width,'height':1000},locale='it-IT' if language=='it' else 'en-GB')
    calls=[];errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/*',serve(web,calls,fail=fail));page.goto('https://mta.test/settings');page.wait_for_load_state('networkidle')
    supplied=os.environ.get('MTA_TEST_AXE_CORE')
    if not supplied:browser.close();manager.stop();pytest.skip('Test-only axe-core required for acceptance')
    page.add_script_tag(path=supplied)
    return manager,browser,page,web,calls,errors


def activate(page,selector):
    page.locator(selector).focus();page.keyboard.press('Enter');page.wait_for_load_state('networkidle')


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_visible_unique_retention_quota_and_cancelled_deletion(account,provider,monkeypatch,nc_browser_config,language,width):
    storage.create_project('Private local fixture',owner_user_id=account)
    manager,browser,page,web,calls,errors=start(account,monkeypatch,nc_browser_config,language,width)
    try:
        page.on('dialog',lambda dialog:dialog.dismiss())
        activate(page,'[data-tab=users]')
        assert page.locator('#accountSandboxDays').count()==page.locator('#accountProjectDays').count()==1
        page.locator('#accountSandboxDays').fill('123');page.locator('#accountProjectDays').fill('45')
        with page.expect_response(lambda r:r.url.endswith('/api/admin/account-lifecycle/settings') and r.request.method=='PUT') as saved:
            activate(page,'button[onclick="saveAccountRetention()"]')
        assert saved.value.status==200,saved.value.text()
        assert saved.value.request.post_data_json=={'sandbox_days':123,'project_days':45}
        assert account_lifecycle.settings()=={'sandbox_days':123,'project_days':45}
        activate(page,f'tr[data-user-id="{account}"] button.danger')
        assert auth.get_user(account) and not any(m=='DELETE' for m,_,_ in calls)
        scan(page,f'workflow-{language}-{width}-retention')
        activate(page,'[data-tab=storage]');page.locator(f'#quota-{account}').fill('700')
        with page.expect_response(lambda r:r.url.endswith(f'/api/admin/users/{account}') and r.request.method=='PATCH') as saved:
            activate(page,f'button[onclick*="setQuota({account},"]')
        assert saved.value.status==200,saved.value.text()
        assert auth.get_user(account)['workspace_quota_bytes']==700*1024*1024
        scan(page,f'workflow-{language}-{width}-quota')
        assert not errors and not any(s>=400 for _,_,s in calls)
    finally:browser.close();manager.stop()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_other_administration_read_errors_remain_named_and_retryable(account,provider,monkeypatch,nc_browser_config,language,width):
    fail=set();manager,browser,page,web,calls,errors=start(account,monkeypatch,nc_browser_config,language,width,fail)
    try:
        cases=[
            ('web','/api/admin/web-settings','#webSettingsSummary'),
            ('web','/api/admin/social-login','#socialStatus'),
            ('models','/api/admin/demucs-models','#modelsBody [role=alert]'),
            ('aiQueue','/api/admin/ai-execution/jobs','#aiQueueBody [role=alert]'),
            ('diagnostics','/api/admin/diagnostics/settings','#diagnosticsStatus'),
            ('legal','/api/admin/legal-settings','#legalStatus'),
            ('subscriptions','/api/admin/subscriptions','#subscriptionsTab [role=status]'),
        ]
        for tab,endpoint,status in cases:
            fail.add(endpoint)
            # Fresh document also checks initial failures before a successful read.
            page.goto('https://mta.test/settings');page.wait_for_load_state('networkidle');page.add_script_tag(path=os.environ['MTA_TEST_AXE_CORE'])
            activate(page,f'[data-tab={tab}]')
            page.wait_for_function("s=>{const e=document.querySelector(s);return e&&e.textContent.trim()}",arg=status)
            scan(page,f'error-{language}-{width}-extra-{endpoint.rsplit("/",1)[1]}')
            fail.clear();activate(page,f'[data-tab={tab}]')
            if tab=='models':page.locator('#modelsBody button').first.wait_for()
            if tab=='subscriptions':page.locator('[data-paypal-save]').wait_for(state='attached')
            scan(page,f'error-{language}-{width}-extra-{endpoint.rsplit("/",1)[1]}-recovered')
        for name,endpoint,status,refresh in [
            ('ai-billing','/api/admin/ai-billing/report','#alert','#load'),
            ('ai-tokens','/api/admin/ai-tokens','#message','#refresh'),
        ]:
            fail.add(endpoint);page.goto('https://mta.test/admin/'+name);page.wait_for_load_state('networkidle');page.add_script_tag(path=os.environ['MTA_TEST_AXE_CORE'])
            page.wait_for_function("s=>document.querySelector(s)?.textContent.trim()",arg=status)
            scan(page,f'error-{language}-{width}-{name}')
            fail.clear();activate(page,refresh)
            scan(page,f'error-{language}-{width}-{name}-recovered')
        assert not errors and not any(m!='GET' for m,_,_ in calls)
    finally:browser.close();manager.stop()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_search_selected_contract_and_permission_readback(account,provider,monkeypatch,nc_browser_config,language,width):
    manager,browser,page,web,calls,errors=start(account,monkeypatch,nc_browser_config,language,width)
    try:
        activate(page,'[data-tab=subscriptions]')
        page.locator('[data-search]').fill('quota-user');page.locator('[data-user-results] button').wait_for()
        page.locator('[data-search]').focus();page.keyboard.press('ArrowDown');page.keyboard.press('Enter')
        page.locator('[data-save-policy]').wait_for(state='attached')
        page.evaluate("document.querySelectorAll('#subscriptionsTab details').forEach(d=>d.open=true)")
        scan(page,f'workflow-{language}-{width}-selected-contract')
        page.locator('[data-allowed]').uncheck()
        with page.expect_response(lambda r:r.url.endswith('/policy') and r.request.method=='PATCH') as saved:
            activate(page,'[data-save-policy]')
        assert saved.value.status==200,saved.value.text()
        assert web.get(f'/api/admin/subscriptions/users/{account}').json()['policy']['subscriptions_allowed']==0
        page.evaluate("document.querySelectorAll('#subscriptionsTab details').forEach(d=>d.open=true)")
        assert not page.locator('[data-allowed]').is_checked()
        scan(page,f'workflow-{language}-{width}-policy-readback')
        assert not errors and not any(s>=400 for _,_,s in calls)
    finally:browser.close();manager.stop()


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_one_time_token_create_rotate_revoke_and_keyboard_hide(account,provider,monkeypatch,nc_browser_config,language,width):
    manager,browser,page,web,calls,errors=start(account,monkeypatch,nc_browser_config,language,width)
    try:
        page.on('dialog',lambda dialog:dialog.accept())
        page.goto('https://mta.test/admin/ai-tokens');page.wait_for_load_state('networkidle');page.add_script_tag(path=os.environ['MTA_TEST_AXE_CORE'])
        page.locator('#uid').select_option(str(account));page.locator('#label').fill('Local keyboard fixture')
        with page.expect_response(lambda r:r.url.endswith('/api/admin/ai-tokens') and r.request.method=='POST') as saved:
            activate(page,'#createButton')
        assert saved.value.status==200,saved.value.text()
        page.locator('#secretBox').wait_for();first=page.locator('#secret').inner_text();assert ai_access.authenticate(first)['user_id']==account
        assert page.locator('#copyToken').evaluate('e=>e===document.activeElement')
        activate(page,'#hideToken');assert page.locator('#secret').inner_text()=='' and page.locator('#secretBox').is_hidden()
        assert page.locator('#label').evaluate('e=>e===document.activeElement')
        scan(page,f'workflow-{language}-{width}-token-created-hidden')
        with page.expect_response(lambda r:r.url.endswith('/rotate') and r.request.method=='POST') as saved:
            activate(page,'#entries tr button:not(.danger)')
        assert saved.value.status==200,saved.value.text()
        page.locator('#secretBox').wait_for();second=page.locator('#secret').inner_text()
        assert second!=first and ai_access.authenticate(first) is None and ai_access.authenticate(second)['user_id']==account
        activate(page,'#hideToken')
        with page.expect_response(lambda r:'/api/admin/ai-tokens/' in r.url and r.request.method=='DELETE') as saved:
            activate(page,'#entries button.danger')
        assert saved.value.status==200,saved.value.text()
        assert ai_access.authenticate(second) is None
        page.wait_for_function("()=>document.activeElement===document.querySelector('#refresh')")
        assert page.locator('#revokedCount').inner_text()=='2'
        assert page.locator('#activeCount').inner_text()=='0'
        scan(page,f'workflow-{language}-{width}-token-revoked')
        # Secrets are deliberately absent during every stored axe scan.
        assert not errors and not any(s>=400 for _,_,s in calls)
    finally:browser.close();manager.stop()


@pytest.mark.parametrize('endpoint,tab,status',[
    ('/api/admin/users','users','#usersBody [role=alert]'),
    ('/api/storage','storage','#storageSummary[role=alert]'),
    ('/api/admin/smtp','smtp','#smtpLoadStatus'),
])
@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_failed_read_clears_stale_controls_and_keyboard_retry(account,provider,monkeypatch,nc_browser_config,language,width,endpoint,tab,status):
    storage.create_project('Private local fixture',owner_user_id=account)
    fail=set();manager,browser,page,web,calls,errors=start(account,monkeypatch,nc_browser_config,language,width,fail)
    try:
        activate(page,f'[data-tab={tab}]')
        fail.add(endpoint);activate(page,f'[data-tab={tab}]')
        page.wait_for_function("s=>document.querySelector(s)?.textContent.trim()",arg=status)
        assert page.locator(status).inner_text().strip()
        if tab=='users':assert page.locator('#usersBody select').count()==0
        if tab=='storage':assert page.locator('#storageBody input').count()==0
        if tab=='smtp':assert page.locator('#smtpForm input:enabled,#smtpSendTest:enabled').count()==0
        scan(page,f'error-{language}-{width}-{tab}')
        fail.clear();activate(page,'[data-smtp-refresh]' if tab=='smtp' else f'[data-tab={tab}]')
        if tab=='users':page.locator('#usersBody select').first.wait_for()
        if tab=='storage':page.locator('#storageBody input').first.wait_for()
        if tab=='smtp':
            page.locator('#smtpForm input:enabled').first.wait_for()
            assert not page.locator('#smtpLoadStatus').inner_text()
        scan(page,f'error-{language}-{width}-{tab}-recovered')
        assert not errors and not any(m!='GET' for m,_,_ in calls)
    finally:browser.close();manager.stop()
