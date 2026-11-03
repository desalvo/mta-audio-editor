"""SAM is retired at catalogs, saved state, request and native boundaries."""
import importlib.util
import json
from pathlib import Path
import subprocess
import threading

import pytest
from fastapi.testclient import TestClient
from app import ai_adapter_identity as identity,ai_install_catalog as install_catalog
from app import ai_unified_adapter as unified,ai_worker_registry as registry,main
from app import model_license_policy as policy,model_rights_dossiers as dossiers
from app import model_selectors,native_ai_routing as native,storage
from test_r210_media_stems_cleanup import project as project,wav  # noqa: F401

ROOT=Path(__file__).parents[1]
REMOVED=('sam-audio','singer-separation')

@pytest.mark.parametrize('kind',REMOVED)
def test_retired_kinds_have_no_active_catalog_or_worker(kind):
    assert kind not in registry.WORKER_KINDS
    assert kind not in unified.SUPPORTED
    assert kind not in install_catalog.ENGINE_GROUPS
    assert kind not in identity.UNIFIED_KINDS
    assert kind not in native.KINDS
    assert 'sam-audio' not in policy.CATALOG and 'sam-audio' not in dossiers.DOSSIERS
    with pytest.raises(ValueError,match='Unsupported'):registry.resolve_worker(kind)
    with pytest.raises(ValueError,match='removed'):policy.evaluate(kind,{})

@pytest.mark.parametrize('kind',REMOVED)
def test_extension_cannot_resurrect_reserved_retired_kind(tmp_path,monkeypatch,kind):
    path=tmp_path/'workers.json';path.write_text(json.dumps([{'kind':kind}]))
    monkeypatch.setenv('MTA_AI_ENGINE_REGISTRY_FILE',str(path))
    with pytest.raises(ValueError,match='Invalid|duplicate'):registry.extensions()

@pytest.mark.parametrize('route',['track','import'])
@pytest.mark.parametrize('query',[
    {'percussion_method':'sam-audio-small'},{'percussion_method':'sam-audio-base'},
    {'percussion_method':'sam-audio-large'},{'singers_json':'[{"id":"singer_1"}]'},
    {'singer_model':'sam-audio-small'},{'singer_target':'all'},
])
def test_legacy_request_rejected_before_copy_runtime_or_project_effects(project,monkeypatch,route,query):
    def forbidden(*a,**k):pytest.fail('Removed request reached a side effect')
    monkeypatch.setattr(main,'_copy_limited',forbidden)
    monkeypatch.setattr(main,'_stem_runtime_status',forbidden)
    monkeypatch.setattr(main.STEM_SPLITTER,'available',forbidden)
    monkeypatch.setattr(main.STEM_SPLITTER,'split',forbidden)
    client=TestClient(main.app,headers={'x-mta-request':'1'})
    if route=='track':response=client.post(f'/api/projects/{project.id}/tracks/missing/stem-jobs',params=query)
    else:response=client.post('/api/stems/jobs',params={'project_id':project.id,**query},files={'file':('source.mp3',b'not-decoded','audio/mpeg')})
    assert response.status_code==410,response.text
    assert 'removed' in response.text and not main.STEM_JOBS
    assert not storage.load_project(project.id).tracks

@pytest.mark.parametrize('kind',REMOVED)
def test_saved_native_route_rejected_before_audio_or_transport(tmp_path,monkeypatch,kind):
    monkeypatch.setattr(native,'_read',lambda:{'workers':{kind:{'mode':'remote','url':'https://example.test','token':'private'}}})
    assert kind not in native.public_settings()['workers']
    with pytest.raises(ValueError,match='removed'):main._ai_external_engine(kind)
    with pytest.raises(ValueError,match='removed'):main._native_remote_infer(kind,tmp_path/'missing.wav',{})
    with pytest.raises(ValueError,match='removed'):native.infer(kind,tmp_path/'missing.wav',{})
    assert not (tmp_path/'missing.wav').exists()

@pytest.mark.parametrize('legacy',[{'singer_mode':True,'singers':[{'id':'singer_1'}]}, {'percussion_method':'sam-audio-large'}])
def test_queued_legacy_work_fails_before_probe_or_publication(project,monkeypatch,legacy):
    source=wav(storage.audio_path(project.id,'source.wav'))
    options={'model':'htdemucs_6s','stem_count':6,'stem_targets':['all'],'percussion_method':'dsp',**legacy}
    payload={'schema_version':1,'project_id':project.id,'source_category':'audio','source_name':source.name,'keep_original_track':True,'options':options}
    with pytest.raises(ValueError,match='removed or unsupported'):main._restore_stem_split_job(project.id,payload,'a'*16)
    assert not main.STEM_JOBS
    monkeypatch.setattr(main,'ffprobe',lambda *a,**k:pytest.fail('Removed queued work probed source'))
    main.STEM_JOBS['a'*16]={'id':'a'*16,'project_id':project.id,'cancel_event':threading.Event(),**options}
    main._stem_split_worker('a'*16,source,True)
    assert main.STEM_JOBS['a'*16]['status']=='failed'
    assert 'removed or unsupported' in main.STEM_JOBS['a'*16]['error']
    assert not storage.load_project(project.id).tracks

def test_removed_sources_are_absent_from_native_and_module_discovery():
    spec=(ROOT/'native/mta_audio_editor_native.spec').read_text()
    for name in ('sam_audio_worker','sam_audio_compat'):
        assert not (ROOT/'app'/f'{name}.py').exists()
        assert importlib.util.find_spec('app.'+name) is None
        assert name not in spec

def test_installer_rejects_removed_group_before_effect_and_cleans_only_retired_bindings(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('retirement_installer',ROOT/'scripts/install_ai_engines.py')
    installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
    monkeypatch.setattr(installer,'run',lambda *a,**k:pytest.fail('Removed group reached installer process'))
    with pytest.raises(ValueError,match='Unsupported'):installer.install_group('/python',tmp_path/'missing','cpu','sam')
    assert not (tmp_path/'missing').exists()
    original='SMTP_HOST=mail.example.test\nHF_HOME=/models/hf\nMTA_DEMUCS_DEVICE=cuda\nMTA_SAM_AUDIO_PYTHON=/old/python\nMTA_AI_SAM_MODEL=sam-audio-large\nMTA_AI_WORKER_SAM_AUDIO_PYTHON=/old/python\nMTA_AI_WORKER_SINGER_SEPARATION_EXECUTABLE=/old/worker\n'
    path=tmp_path/'service.env';path.write_text(original)
    installer.update_environment(path,{'MTA_AI_WORKER_ENABLED':'true'},original)
    assert 'SMTP_HOST=mail.example.test' in path.read_text()
    assert 'HF_HOME=/models/hf' in path.read_text() and 'MTA_DEMUCS_DEVICE=cuda' in path.read_text()
    assert not any('SAM_' in line or 'SINGER_SEPARATION_' in line for line in path.read_text().splitlines())

@pytest.mark.parametrize('model',['sam-audio-small','facebook/sam-audio-large'])
def test_legacy_drumsep_selector_cannot_fall_back_to_another_engine(model):
    with pytest.raises(ValueError,match='removed'):model_selectors.validate_selection('drumsep',{'model':model})
    with pytest.raises(ValueError,match='removed'):policy.selected('drumsep',{'model':model})

def test_actual_native_preferences_do_not_migrate_removed_singer_choices():
    script=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const items=new Map([['mtaStemCount','6'],['mta.singer.model','sam-audio-large'],['mta.singer.target','singer_1']]);
const local={get length(){return items.size},key:i=>[...items.keys()][i],getItem:k=>items.get(k)??null,setItem:(k,v)=>items.set(k,v)};
const window={localStorage:local,addEventListener(){}};
const context={window,document:{getElementById:()=>({textContent:JSON.stringify({owner:'native',values:{}})})},setTimeout:()=>1,clearTimeout(){},TextEncoder};
vm.runInNewContext(fs.readFileSync('app/static/user_preferences.js','utf8'),context);
assert.equal(window.MtaPreferences.getItem('mta.singer.model'),null);
assert.equal(window.MtaPreferences.getItem('mta.singer.target'),null);
assert.equal(window.MtaPreferences.getItem('mtaStemCount'),'6');
'''
    result=subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True,timeout=15,check=False)
    assert result.returncode==0,result.stderr
