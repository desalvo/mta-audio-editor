"""MR-MT3 routing/admission contracts; substitutes never certify neural quality."""
import json
from pathlib import Path
import sys
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app import ai_studio_adapter, model_license_policy as policy, studio_catalog
from app.music_interchange import MusicPart, MusicResult, parse_result
from app.models import MidiNote, Project, Track


@pytest.fixture
def adapter_contract(monkeypatch):
    module=types.ModuleType('app.mrmt3_adapter')
    module.python_for=lambda:None
    module.transcribe=lambda source,options:pytest.fail('No inference expected')
    monkeypatch.setitem(sys.modules,'app.mrmt3_adapter',module)
    return module


def music():
    return MusicResult(parts=[MusicPart(id='p',name='Piano',program=0,
        notes=[MidiNote(id='n',pitch=60,start_ms=0,duration_ms=100)])])


def test_optional_backend_has_no_basic_pitch_fallback(adapter_contract,monkeypatch):
    from app import ai_worker_registry as registry
    monkeypatch.setenv('MTA_STUDIO_TRANSCRIBER','mr-mt3')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true')
    monkeypatch.delenv('MTA_AI_WORKER_AUDIO_TO_MIDI_MR_MT3_EXECUTABLE',raising=False)
    monkeypatch.delenv('MTA_AI_ENGINE_REGISTRY_FILE',raising=False)
    monkeypatch.setattr(studio_catalog,'receipt',lambda:pytest.fail('MR-MT3 must not fall back to Basic Pitch'))
    assert 'audio-to-midi-mr-mt3' in registry.registered_kinds()
    assert studio_catalog.python_for('audio-to-midi') is None
    assert studio_catalog.python_for('audio-to-midi-mr-mt3') is None
    assert registry.resolve_worker('audio-to-midi-mr-mt3') is None


def test_verified_interpreter_is_delegated_without_changing_default(adapter_contract,monkeypatch):
    from app import ai_worker_registry as registry
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true')
    monkeypatch.delenv('MTA_AI_WORKER_AUDIO_TO_MIDI_MR_MT3_EXECUTABLE',raising=False)
    monkeypatch.delenv('MTA_AI_WORKER_AUDIO_TO_MIDI_MR_MT3_PYTHON',raising=False)
    adapter_contract.python_for=lambda:Path(sys.executable)
    assert studio_catalog.python_for('audio-to-midi-mr-mt3')==sys.executable
    assert registry.resolve_worker('audio-to-midi-mr-mt3').name=='ai_studio_adapter.py'
    assert registry.worker_python('audio-to-midi-mr-mt3')==sys.executable
    monkeypatch.setenv('MTA_STUDIO_TRANSCRIBER','mr-mt3')
    assert studio_catalog.python_for('audio-to-midi')==sys.executable
    monkeypatch.setenv('MTA_STUDIO_TRANSCRIBER','basic-pitch')
    monkeypatch.setattr(studio_catalog,'receipt',lambda:None)
    assert studio_catalog.python_for('audio-to-midi') is None


@pytest.mark.parametrize('kind',['audio-to-midi-mr-mt3','audio-to-midi'])
def test_dispatch_preserves_programs_in_worker_result(adapter_contract,monkeypatch,tmp_path,kind):
    from model_rights_fixtures import authorize_fixture
    authorize_fixture(monkeypatch,tmp_path,'mr-mt3-assets')
    monkeypatch.setenv('MTA_STUDIO_TRANSCRIBER','mr-mt3')
    source=tmp_path/'source.wav';source.write_bytes(b'contract-only source, not neural audio')
    expected=music();expected.parts[0].program=40;calls=[]
    def transcribe(path,options):calls.append((path,options));return expected
    adapter_contract.transcribe=transcribe
    monkeypatch.setattr(ai_studio_adapter,'transcribe',lambda *a:pytest.fail('Wrong Basic Pitch backend'))
    ai_studio_adapter.infer({'kind':kind,'source_audio':str(source),'options':{'name':'Reviewed source'}},tmp_path/'preview.wav')
    assert calls==[(source,{'name':'Reviewed source'})]
    assert parse_result((tmp_path/'music.json').read_bytes()).parts[0].program==40


def test_model_rights_are_independent_and_disabled_by_default(monkeypatch):
    monkeypatch.setattr(policy,'overrides',lambda:{})
    assert policy.selected('audio-to-midi-mr-mt3',{})=='mr-mt3-assets'
    monkeypatch.setenv('MTA_STUDIO_TRANSCRIBER','mr-mt3')
    assert policy.selected('audio-to-midi',{})=='mr-mt3-assets'
    assert 'mr-mt3-assets' in policy.RESTRICTED_MODELS
    with pytest.raises(policy.LicenseDenied,match='pending license review'):
        policy.evaluate('audio-to-midi-mr-mt3',{})


@pytest.fixture
def submission(monkeypatch,tmp_path):
    from app import ai_worker_registry, studio_jobs, auth
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path)
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    monkeypatch.setattr(ai_worker_registry,'resolve_worker',lambda kind:Path(__file__))
    calls=[]
    monkeypatch.setattr(policy,'evaluate',lambda kind,plan:(calls.append(('policy',kind)),policy.Decision('mr-mt3-assets','cost_recovery','fixture','a'*64))[1])
    monkeypatch.setattr(studio_jobs.queue,'start',lambda *a,**kw:(calls.append(('queue',kw['payload'])),(True,{'id':kw['job_id']}))[1])
    project=Project(id='fixture',title='Fixture',target='DAW_MIDI',project_kind_version=1,tracks=[Track(id='source',name='Mix',filename='mix.wav',kind='audio')])
    app=FastAPI();studio_jobs.register_routes(app,lambda request,pid:project,lambda request:{'id':7,'role':'user'},lambda *a:None)
    return TestClient(app),calls


def test_explicit_request_reaches_own_policy_and_queue(submission):
    client,calls=submission
    response=client.post('/api/projects/fixture/ai-studio/jobs',json={'operation':'audio-to-midi','transcriber':'mr-mt3','track_ids':['source'],'end_ms':1000})
    assert response.status_code==200,response.text
    assert ('policy','audio-to-midi-mr-mt3') in calls
    payload=next(value for kind,value in calls if kind=='queue')
    assert payload['request']['transcriber']=='mr-mt3' and payload['request']['mode']=='fast'


@pytest.mark.parametrize('overrides',[{'settings':{'onset_threshold':.5}},{'programs':{'source':0}}])
def test_classifier_rejects_basic_pitch_overrides_before_queue(submission,overrides):
    client,calls=submission
    response=client.post('/api/projects/fixture/ai-studio/jobs',json={'operation':'audio-to-midi','transcriber':'mr-mt3','track_ids':['source'],'end_ms':1000,**overrides})
    assert response.status_code==422 and 'instrument identity' in response.text
    assert not any(kind=='queue' for kind,_ in calls)


def test_recovery_fingerprint_tracks_mr_runtime_receipt(monkeypatch,tmp_path):
    from app import ai_worker_registry, studio_stage_cache
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    monkeypatch.setenv('MTA_STUDIO_MRMT3_RUNTIME',str(tmp_path))
    monkeypatch.setattr(ai_worker_registry,'resolve_worker',lambda kind:None)
    monkeypatch.setattr(studio_catalog,'root',lambda:tmp_path)
    monkeypatch.setattr(policy,'evaluate',lambda *a:policy.Decision('mr-mt3-assets','free_only','fixture','a'*64))
    path=tmp_path/'mta-runtime.json';path.write_text(json.dumps({'files':{'weights/model.safetensors':'a'*64}}))
    before=studio_stage_cache.fingerprint('audio-to-midi-mr-mt3',{})
    path.write_text(json.dumps({'files':{'weights/model.safetensors':'b'*64}}))
    assert studio_stage_cache.fingerprint('audio-to-midi-mr-mt3',{})!=before


@pytest.mark.parametrize('mode',['accurate','maximum'])
def test_fast_selector_does_not_replace_ensemble_dependencies(submission,monkeypatch,mode):
    from app import ai_worker_registry
    client,calls=submission;resolved=[]
    def resolve(kind):
        resolved.append(kind)
        return None if kind=='audio-to-midi-mr-mt3' else Path(__file__)
    monkeypatch.setattr(ai_worker_registry,'resolve_worker',resolve)
    monkeypatch.setenv('MTA_STUDIO_TRANSCRIBER','mr-mt3')
    response=client.post('/api/projects/fixture/ai-studio/jobs',json={
        'operation':'audio-to-midi','transcriber':'mr-mt3','mode':mode,
        'settings':{'onset_threshold':.6},'track_ids':['source'],'end_ms':1000})
    assert response.status_code==200,response.text
    assert resolved[0]=='audio-to-midi-basic-pitch'
    assert 'audio-to-midi-mr-mt3' not in resolved
    assert ('policy','audio-to-midi') not in calls and ('policy','audio-to-midi-mr-mt3') not in calls
    assert ('policy','audio-to-midi-yourmt3') in calls and ('policy','audio-to-midi-basic-pitch') in calls


def test_selector_readiness_and_fast_only_settings_in_javascript():
    import shutil
    import subprocess
    node=shutil.which('node')
    if not node:pytest.skip('Node.js is required to execute the shared selector')
    source=Path(__file__).resolve().parents[1]/'app/static/studio_extended.js'
    script=r"""
const fs=require('fs'),assert=require('node:assert/strict');
global.window={};global.tr=(a,b)=>a;
const fields={studioTranscriber:{value:'mr-mt3'},studioPianoAsset:{value:''}};
global.document={getElementById:id=>fields[id],createElement:()=>({})};
eval(fs.readFileSync(process.argv[1],'utf8'));
const dialog={dataset:{operation:'audio-to-midi',transcriber:'mr-mt3'},rows:[],append(row){this.rows.push(row)}};
window.mtaStudioEnhancements.mountTranscription(dialog,{models:[{id:'mr-mt3',available:false}]});
assert.match(dialog.rows[0].innerHTML,/<option value="mr-mt3" disabled>/);
window.mtaStudioEnhancements.mountTranscription(dialog,{models:[{id:'mr-mt3',available:true}]});
assert.match(dialog.rows[1].innerHTML,/<option value="mr-mt3" >MR-MT3/);
let request={operation:'audio-to-midi',mode:'fast',settings:{onset_threshold:.6}};
window.mtaStudioEnhancements.augment(request,dialog);
assert.equal(request.transcriber,'mr-mt3');assert.deepEqual(request.settings,{});
request={operation:'audio-to-midi',mode:'accurate',settings:{onset_threshold:.6}};
window.mtaStudioEnhancements.augment(request,dialog);
assert.deepEqual(request.settings,{onset_threshold:.6});
fields.studioTranscriber.value='default';
request={operation:'audio-to-midi',mode:'fast',settings:{onset_threshold:.6}};
window.mtaStudioEnhancements.augment(request,dialog);
assert.deepEqual(request.settings,{});
"""
    subprocess.run([node,'-e',script,str(source)],check=True,capture_output=True,text=True)
