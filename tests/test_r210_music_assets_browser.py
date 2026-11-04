"""Chromium UI regression; backend execution is covered separately with real PCM."""
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import pytest

from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401

playwright=pytest.importorskip('playwright.sync_api')
ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('language',['it','en'])
@pytest.mark.parametrize('native',[False,True])
def test_music_assets_consent_policy_and_singing_request(language,native,nc_browser_config):
    prefix='/api/native/ai/studio' if native else '/api/admin/ai/studio'
    requests=[]
    voices=[{'id':'air','name':'Air Navier','installed':True,'size_bytes':1000}]
    project={'id':'project','tracks':[{'id':'melody','name':'Melody','kind':'midi'}]}
    data={'models':[{'id':'basic-pitch','available':False,'installed':False,'size_bytes':0,'license_url':'https://example.org/license'}],
        'policy':{'timeout_seconds':3600,'retention_days':7},'gm':{'available':False},'voicebanks':voices,
        'licenses':[{'id':'madmom','license':'CC-BY-NC-SA-4.0','mode':'disabled','license_url':'https://example.org/terms'}]}
    with playwright.sync_playwright() as p:
        browser=p.chromium.launch(**nc_browser_config)
        page=browser.new_page(viewport={'width':800,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        def serve(route):
            parsed=urlsplit(route.request.url)
            path=parsed.path
            if path=='/api/ai/studio/capabilities':
                assert parse_qs(parsed.query).get('operation')==['vocal-synthesis']
            if path=='/':route.fulfill(content_type='text/html',body='<div id="modal"></div>');return
            requests.append((path,route.request.method,route.request.post_data_json if route.request.method in ('POST','PUT') else None))
            if path==prefix+'/models':result=data
            elif path==prefix+'/models/gm-pack/install':result={'job_id':'install','job':{}}
            elif path==prefix+'/installations/install':result={'job_id':'install','state':'running','phase':'downloading','message':'1048576 bytes','progress_percent':25}
            elif path==prefix+'/licenses/madmom':
                data['licenses'][0]['mode']=route.request.post_data_json['mode']
                result={'licenses':data['licenses']}
            elif path=='/api/ai/studio/capabilities':result={'voicebanks':voices}
            elif path=='/api/projects/project/ai-studio/jobs':result={'job_id':'singing','job':{}}
            elif path=='/api/projects/project/ai-studio/jobs/singing':result={'job':{'state':'completed','phase':'results-saved','message':'Saved'},'result_available':False}
            elif path=='/api/projects/project':result=project
            else:raise AssertionError(path)
            route.fulfill(content_type='application/json',body=json.dumps(result))
        page.route('https://mta.test/**',serve);page.goto('https://mta.test/')
        page.evaluate('(language)=>document.documentElement.lang=language', language)
        page.add_script_tag(content=f"window.lang={json.dumps(language)};window.currentUser={json.dumps({'role':'admin','native_single_user':native})};window.current={json.dumps(project)};window.selectedTrackId='melody';")
        page.add_script_tag(content="""window.tr=(en,it)=>lang==='it'?it:en;window.api=async(url,options)=>{const r=await fetch(url,options);return r.json()};window.showUtilityModal=(title,html)=>{document.getElementById('modal').innerHTML='<h1>'+title+'</h1>'+html};window.toast=message=>{throw new Error(message)};window.render=()=>{};window.projectEnd=()=>3000;window.flushAutosave=async()=>{};window.MtaPreferences={getItem:()=>null,setItem:()=>{}};window.mtaAiJobs={origin:()=>{},handled:()=>{}};""")
        page.add_script_tag(content=(ROOT/'app/static/ai_studio.js').read_text())
        page.evaluate('openStudioModels()');page.wait_for_selector('[data-asset="gm-pack"]')
        page.locator('[data-assets-consent]').check();page.locator('[data-asset="gm-pack"]').click()
        page.wait_for_function("document.querySelector('.studio-asset progress').value===25")
        assert requests[-2][0].startswith(prefix)
        # Rights controls are owned by settings. Studio retains instruments and voices.
        assert page.locator('[data-license="madmom"]').count()==0
        if native:
            page.add_script_tag(content=(ROOT/'app/static/ai_license_settings.js').read_text())
            editor=(ROOT/'app/static/app.js').read_text()
            start=editor.index('async function showNativeSettings(){')
            end=editor.index('// Settings save',start)
            page.add_script_tag(content="window.waitForNativeApi=async()=>({get_native_settings:async()=>({})});"
                "window.appDisplayPreference=()=>false;window.esc=value=>String(value);"+editor[start:end])
            page.evaluate('showNativeSettings()')
            settings=page.locator('.native-settings [data-native-model-licenses]')
        else:
            template=(ROOT/'app/templates/admin.html').read_text()
            models=template.split('<section id="modelsTab"',1)[1].split('<section id="aiQueueTab"',1)[0]
            assert '<section data-admin-model-licenses></section>' in models
            page.locator('#modal').evaluate("node=>node.innerHTML="
                "'<button data-tab=\"models\">Models</button><section data-admin-model-licenses></section>'")
            page.add_script_tag(content=(ROOT/'app/static/ai_license_settings.js').read_text())
            page.locator('[data-tab="models"]').click()
            settings=page.locator('[data-admin-model-licenses]')
        card=settings.locator('[data-license="madmom"]')
        card.wait_for(state='attached')
        settings.locator('details').filter(has=page.locator('[data-license="madmom"]')).first.locator('summary').first.click()
        card.locator('summary').click()
        card.locator('[data-mode]').select_option('free_only')
        card.locator('[data-reason]').fill('Verified noncommercial permission and free API access')
        card.locator('[data-responsibility]').check()
        card.locator('[data-free]').check()
        with page.expect_response(lambda response: urlsplit(response.url).path==prefix+'/licenses/madmom'
                                  and response.request.method=='PUT') as saved:
            card.locator('[data-license-save]').click()
        assert saved.value.ok
        assert any(path==prefix+'/licenses/madmom' and body['free_access_confirmed'] for path,method,body in requests if method=='PUT')
        playwright.expect(settings.locator('[data-license="madmom"] [data-mode]')).to_have_value('free_only')
        page.evaluate('openVocalSynthesis()');page.wait_for_selector('#studioVoice');page.locator('[data-studio-source]').check();page.locator('#studioRun').click()
        page.wait_for_function("document.querySelector('#studioStatus').textContent.length>0")
        body=next(body for path,method,body in requests if path=='/api/projects/project/ai-studio/jobs' and method=='POST')
        assert body['operation']=='vocal-synthesis' and body['settings']['voicebank']=='air' and body['track_ids']==['melody']
        assert not errors
        browser.close()
