"""Actual native settings API and shipped dialog function, with no remote I/O."""
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from app import native_ai_routing as routing, service_regime
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_legal_documents import cookie
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401


@pytest.mark.parametrize('state',['commercial','nc','unverifiable'])
def test_settings_policy_is_not_connection_or_model_authorization(monkeypatch,state):
    read=Mock(return_value={'workers':{'whisper':{'mode':'remote','url':'https://example.test','token':'PRIVATE_TOKEN'}}})
    monkeypatch.setattr(routing,'_read',read)
    def regime():
        if state=='unverifiable':raise ValueError('private local path')
        return service_regime.Regime.COMMERCIAL if state=='commercial' else service_regime.Regime.NON_COMMERCIAL
    monkeypatch.setattr(service_regime,'current_regime',regime)
    result=routing.public_settings();assert read.call_count==1 and 'PRIVATE_TOKEN' not in str(result)
    assert result['remote_policy']['state']=={'commercial':'blocked_unattested','nc':'model_review_required','unverifiable':'blocked_unverifiable'}[state]
    assert result['remote_policy']['commercial_remote_inference_enabled'] is False


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('width',[390,1280])
def test_shipped_native_dialog_explains_block_but_keeps_existing_work_controls(account,monkeypatch,nc_browser_config,language,width):
    from playwright.sync_api import sync_playwright
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',True)
    monkeypatch.setattr(routing,'_read',lambda:{'workers':{'whisper':{'mode':'remote','url':'https://example.test','token':'PRIVATE_TOKEN'}}})
    owner=TestClient(main.app);owner.cookies.update(cookie(account));calls=[]
    app_js=(Path(__file__).resolve().parents[1]/'app/static/app.js').read_text()
    start=app_js.index('async function openNativeRemoteWorkers(){');end=app_js.index('// Explicit operator workflow',start)
    function=app_js[start:end]
    def serve(route):
        url=urlsplit(route.request.url);assert url.hostname=='mta.test'
        if url.path=='/dialog':
            route.fulfill(content_type='text/html',body='<html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="host"></div></html>');return
        response=owner.get(url.path);calls.append((route.request.method,url.path,response.status_code))
        route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
    with sync_playwright() as api:
        browser=api.chromium.launch(**nc_browser_config);page=browser.new_page(viewport={'width':width,'height':900});page.route('**/*',serve)
        page.goto('https://mta.test/dialog')
        page.add_script_tag(content='''const tr=(en,it)=>LANG==='it'?it:en;
        const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
        const api=async path=>{const r=await fetch(path);if(!r.ok)throw Error('HTTP '+r.status);return r.json()};
        const showUtilityModal=(title,body)=>{document.getElementById('host').innerHTML=body};
        const refreshNativePending=async()=>{};const toast=message=>{throw Error(message)};
        '''.replace('LANG',repr(language))+function)
        page.evaluate('openNativeRemoteWorkers()')
        note=page.locator('[data-remote-rights]');note.wait_for()
        assert ('Nuove inferenze remote bloccate' if language=='it' else 'New remote inference is blocked') in note.inner_text()
        assert page.locator('#nativeRemotePending').count()==1 and page.locator('#nativeRemoteHistory').count()==1
        assert page.locator('#nativeRemoteMode-whisper').input_value()=='remote'
        assert 'PRIVATE_TOKEN' not in page.content()
        assert calls==[('GET','/api/native/ai-workers/settings',200)]
        browser.close()
