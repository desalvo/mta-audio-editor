"""Continuous browser PCM and administrator-only managed plugin removal."""
# ruff: noqa: F811 -- imported pytest fixtures are injected by name
import json
from pathlib import Path
import subprocess
import threading

from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
import pytest

from app import auth,optional_plugins as plugins,storage
from app.models import Track,InsertPlugin
from app.vst3_live import SESSIONS,SESSION_LOCK
from test_r210_cpp_audio_engine import compiled_core  # noqa: F401

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def managed(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'data')
    monkeypatch.setattr(storage,'ROOT',tmp_path/'data')
    monkeypatch.setenv('MTA_OPTIONAL_VST3_DIR',str(tmp_path/'plugins'))
    monkeypatch.setattr(plugins,'_LOCK',threading.Lock())
    spec=plugins.select(['mverb'])[0]
    folder=plugins.plugin_root()/'mverb'/spec['revision'];folder.mkdir(parents=True)
    (folder/'installation.json').write_text('{}')
    bundle=folder/'MVerb.vst3';bundle.mkdir();(bundle/'test.so').write_bytes(b'test fixture')
    cache=auth.data_root()/'optional-plugin-builds'/'mverb'/spec['revision'];cache.mkdir(parents=True)
    (cache/'status.json').write_text(json.dumps({'error':'old failure'}));(cache/'install.log').write_text('build history')
    return folder,bundle,cache


def test_uninstall_removes_only_managed_package_and_cache(managed,tmp_path):
    folder,bundle,cache=managed
    victim=tmp_path/'untouched';victim.mkdir();(victim/'keep').write_text('private project')
    (bundle/'outside').symlink_to(victim,target_is_directory=True)
    (cache/'outside').symlink_to(victim,target_is_directory=True)
    result=plugins.uninstall('mverb',remove_build_cache=True)
    assert result['state']=='not_installed'
    assert not folder.parent.exists() and not cache.parent.exists()
    assert (victim/'keep').read_text()=='private project'
    card=next(p for p in plugins.catalog()['plugins'] if p['id']=='mverb')
    assert not card['installed'] and card['state']=='not_installed'


def test_uninstall_can_keep_sources_and_clear_previous_failure(managed):
    folder,_,cache=managed
    plugins.uninstall('mverb')
    assert not folder.exists() and (cache/'install.log').exists()
    card=next(p for p in plugins.catalog()['plugins'] if p['id']=='mverb')
    assert card['state']=='not_installed' and not card['error']


def test_uninstall_reports_project_references_and_refuses_active_host(managed):
    _,bundle,_=managed
    project=storage.create_project('Dependent')
    project.tracks=[Track(id='t',name='Tone',filename='tone.wav',duration_ms=1000,inserts=[InsertPlugin(id='v',plugin='vst3',params={'path':str(bundle)})])]
    path=storage.pdir(project.id)/'project.json';path.write_text(project.model_dump_json());before=path.read_bytes()
    class Live:
        closed=False
    session=Live();session.project=project
    with SESSION_LOCK:SESSIONS.add(session)
    try:
        info=plugins.uninstall_info('mverb')
        assert info['in_use'] and info['projects']==[{'id':project.id,'title':'Dependent'}]
        with pytest.raises(ValueError,match='Stop playback'):plugins.uninstall('mverb')
        assert bundle.exists()
    finally:
        with SESSION_LOCK:SESSIONS.discard(session)
    plugins.uninstall('mverb');assert path.read_bytes()==before


@pytest.mark.parametrize('identifier',['../mverb','/outside','mverb/../../outside','unknown'])
def test_uninstall_cannot_select_arbitrary_paths(managed,identifier):
    with pytest.raises(ValueError):plugins.uninstall(identifier)
    assert managed[0].exists()


def test_uninstall_rejects_symlinked_root_and_concurrent_installer(managed,tmp_path):
    folder,_,_=managed
    assert plugins._LOCK.acquire(blocking=False)
    try:
        with pytest.raises(ValueError,match='installation'):plugins.uninstall('mverb')
    finally:plugins._LOCK.release()
    package=folder.parent;detached=tmp_path/'external';package.rename(detached);package.symlink_to(detached,target_is_directory=True)
    with pytest.raises(ValueError,match='Unsafe'):plugins.uninstall('mverb')
    assert (detached/folder.name/'installation.json').exists()


def test_operator_route_requires_authorization_and_explicit_confirmation(managed,monkeypatch):
    from app.optional_plugin_routes import router
    app=FastAPI();app.include_router(router)
    def admin(request):
        if request.headers.get('x-test-role')!='admin':raise HTTPException(403)
    monkeypatch.setattr(auth,'require_admin',admin)
    client=TestClient(app);path='/api/admin/optional-vst3/mverb/uninstall'
    assert client.get(path).status_code==403
    assert client.post(path,json={'confirm':True,'remove_build_cache':True}).status_code==403
    headers={'x-test-role':'admin'}
    assert client.get(path,headers=headers).json()['installed']
    assert client.post(path,headers=headers,json={'confirm':False,'remove_build_cache':True}).status_code==422
    assert managed[0].exists()
    assert client.post(path,headers=headers,json={'confirm':True,'remove_build_cache':True}).status_code==200
    assert not managed[0].exists()


def test_pcm_sample_continuity_and_resampling():
    result=subprocess.run(['node','tests/server_pcm_continuity.cjs'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr


def test_cpp_browser_survives_jitter_and_gui_stalls(compiled_core,tmp_path):
    pytest.importorskip('playwright.sync_api');pytest.importorskip('pedalboard');pytest.importorskip('av')
    from scripts.validate_cpp_live_controls import probe
    result=probe(compiled_core,tmp_path/'continuity.json',stress=True)
    assert result['stream']['mode']=='worklet' and result['stream']['underruns']==0


@pytest.mark.parametrize('locale',['en','it'])
def test_uninstall_button_confirmation_and_state(locale):
    api=pytest.importorskip('playwright.sync_api')
    with api.sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page();requests=[]
        page.route('http://mta.test/',lambda r:r.fulfill(body='<div id="catalog"></div>',content_type='text/html'));page.goto('http://mta.test/')
        page.evaluate('(locale)=>{window.MtaLocale={language:locale}}',locale)
        data=plugins.catalog();data['active_job']=None
        for p in data['plugins']:p.update(installed=p['id']=='mverb',state='installed' if p['id']=='mverb' else 'not_installed',error='')
        page.route('**/api/admin/optional-vst3',lambda r:r.fulfill(json=data))
        def uninstall(route):
            requests.append((route.request.method,route.request.post_data_json if route.request.method=='POST' else None))
            if route.request.method=='GET':route.fulfill(json={'installed':True,'in_use':False,'projects':[{'id':'p','title':'Dependent'}]})
            else:route.fulfill(json={'id':'mverb','state':'not_installed'})
        page.route('**/api/admin/optional-vst3/mverb/uninstall',uninstall)
        page.add_script_tag(content=(ROOT/'app/static/optional_plugins.js').read_text());page.evaluate('()=>{void openOptionalVst3(document.getElementById("catalog"))}')
        card=page.locator('[data-plugin=mverb]');button=card.get_by_role('button',name='Disinstalla' if locale=='it' else 'Uninstall',exact=True)
        assert button.is_visible();assert page.locator('[data-plugin=dragonfly] .optional-plugin-uninstall').is_hidden()
        page.once('dialog',lambda d:d.dismiss());button.click();page.wait_for_timeout(50)
        assert not any(method=='POST' for method,_ in requests)
        page.once('dialog',lambda d:d.accept());button.click();page.locator('[data-plugin=mverb][data-state=not_installed]').wait_for()
        assert button.is_hidden();assert requests[-1]==('POST',{'confirm':True,'remove_build_cache':True});browser.close()


def test_pending_uninstall_is_not_discoverable_or_executable(tmp_path,monkeypatch):
    from app.vst3_host import discover_plugins,validate_plugin_path
    root=tmp_path/'plugins';root.mkdir(mode=0o755)
    bundle=root/'.mta-vst3-remove-test'/'Example.vst3';bundle.mkdir(parents=True)
    monkeypatch.setenv('MTA_VST3_PATHS',str(root));monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    assert not any(item['path']==str(bundle) for item in discover_plugins())
    with pytest.raises(ValueError,match='uninstalled'):validate_plugin_path(str(bundle))


def test_contiguous_decoder_does_not_seek_for_every_block(tmp_path,monkeypatch,compiled_core):
    import numpy as np
    import soundfile as sf
    from app import cpp_audio
    from app.models import Project,Clip
    from app.vst3_live_graph import Graph
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));cpp_audio._load.cache_clear()
    source=tmp_path/'tone.wav';sf.write(source,np.full((96000,2),.2,dtype=np.float32),48000,subtype='FLOAT')
    real=sf.SoundFile;seeks=[]
    class Reader:
        def __init__(self,path):self.file=real(path)
        def __getattr__(self,name):return getattr(self.file,name)
        def seek(self,position):seeks.append(position);return self.file.seek(position)
    monkeypatch.setattr(sf,'SoundFile',Reader)
    p=Project(id='sequential',title='Sequential decoder',sample_rate=48000,tracks=[Track(id='t',name='Tone',filename='tone.wav',channels=2,duration_ms=2000,clips=[Clip(id='c',source_end_ms=2000)])])
    graph=Graph(p,[source],raw_sources=['t'])
    try:
        data=graph.read(8192)
        np.testing.assert_allclose(data,.2,atol=1e-6)
        assert len(seeks)<=2,'Adjacent decoder blocks must use sequential reads'
    finally:graph.close()


def test_uninstall_blocks_an_open_independent_native_editor(managed,monkeypatch):
    from app import vst3_editor
    class Process:
        def poll(self):return None
    monkeypatch.setattr(vst3_editor,'_JOBS',{'editor':(Process(),None,None)})
    assert plugins.uninstall_info('mverb')['in_use']
    with pytest.raises(ValueError,match='desktop plugin editor'):plugins.uninstall('mverb')
    assert managed[0].exists()
