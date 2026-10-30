"""All model domains reject incomplete restored grants;legacy work stays gated."""
import importlib.util
import hashlib
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock
from contextlib import nullcontext

import pytest
from app import auth,model_license_policy as policy
from model_rights_fixtures import synthetic_review
from test_r210_execution_entry_acceptance import (
    KINDS, api, audio, env as env, registered as registered,  # noqa: F401
)

ROOT=Path(__file__).resolve().parents[1]
MODELS=sorted(set(policy.CATALOG)|{'operator-fixture'})


@pytest.mark.parametrize('kind',KINDS)
@pytest.mark.parametrize('transport',['json','upload'])
@pytest.mark.parametrize('grant',[{'mode':'disabled'},{'mode':'free_only'}])
def test_every_registered_token_api_refuses_unreviewed_permission_before_execution(env,registered,rights,tmp_path,monkeypatch,kind,transport,grant):
    from app import ai_access
    plan={}
    if kind=='backing-vocals':plan['model']='mvsep-mega53'
    if kind=='drumsep':plan['model']='dsp'
    if kind=='chords-ml':plan['engine']='profile-fast'
    if kind=='audio-to-midi-transkun':
        from test_r210_managed_execution_identity import install_at
        install_at(tmp_path/'models',monkeypatch)
        plan['options']={'asset_id':'identity-piano'}
    model=policy.selected(kind,plan)
    rights.write_text(json.dumps({model:grant}))
    token=ai_access.issue(env,'Denied restored permission fixture')
    headers={'Authorization':'Bearer '+token['token']}
    with api() as client:
        if transport=='json':
            response=client.post('/api/ai-jobs/execute',json={'kind':kind,'plan':plan},headers=headers)
        else:
            source=audio();media='audio/wav'
            if kind in ('vocal-harmony','vocal-synthesis'):
                from test_r210_studio_large_remote_options import score
                source=score();media='application/vnd.mta.score+json'
            headers.update({'Content-Type':media,'X-MTA-AI-Options':base64.urlsafe_b64encode(json.dumps(plan).encode()).decode()})
            response=client.post('/api/ai-jobs/execute-audio/'+kind,content=source,headers=headers)
    assert response.status_code==400,response.text
    assert ('Model disabled pending license review' in response.text or 'complete recorded operator review' in response.text),response.text
    assert not registered[1].exists()
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]==0


@pytest.fixture
def rights(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'auth')
    path=tmp_path/'license-policy.json';monkeypatch.setattr(policy,'_path',lambda:path)
    return path


@pytest.mark.parametrize('model',MODELS)
@pytest.mark.parametrize('field',['evidence_url','reason','acknowledge_responsibility','free_access_confirmed','actor_id','reviewed_at'])
def test_every_model_rejects_restored_review_with_a_missing_required_field(rights,model,field):
    review=synthetic_review('free_only');review.pop(field)
    rights.write_text(json.dumps({model:review}))
    with pytest.raises(policy.LicenseDenied):policy.evaluate_model(model)


@pytest.mark.parametrize('value',[{},None,[],{'mode':'cost_recovery'}])
def test_restricted_model_cannot_be_enabled_by_bare_or_malformed_override(rights,value):
    rights.write_text(json.dumps({'uvr-kara-2':value}))
    with pytest.raises(policy.LicenseDenied):policy.evaluate_model('uvr-kara-2')


@pytest.mark.parametrize('body',['{"whisper":{},"whisper":{}}','{"whisper":{"mode":"disabled","mode":"cost_recovery"}}',
                               '{"whisper":{"mode":"cost_recovery","reviewed_at":NaN}}'])
def test_ambiguous_json_is_not_a_license_permission(rights,body):
    rights.write_text(body)
    with pytest.raises(policy.LicenseDenied):policy.evaluate_model('whisper')


@pytest.mark.parametrize('model',MODELS)
def test_complete_synthetic_review_is_consumed_without_real_weight_installation(rights,model):
    rights.write_text(json.dumps({model:synthetic_review('free_only')}))
    decision=policy.evaluate_model(model)
    assert decision.model_id==model and not decision.billable and decision.operator_review


@pytest.mark.parametrize('model',['uvr-kara-2','audio-separator-weights','chordformer','drumsep-weights'])
def test_noncommercial_label_cannot_complete_unknown_checkpoint_rights(rights,model):
    review=synthetic_review('free_only');review['authorization_basis']='noncommercial_context'
    rights.write_text(json.dumps({model:review}))
    rights.with_name('commercial-service.json').write_text('{"enabled":false}')
    with pytest.raises(policy.LicenseDenied,match='actual reviewed authorization'):policy.evaluate_model(model)


@pytest.mark.parametrize('field,value',[
    ('actor_id',True),('actor_id',-1),('reviewed_at',False),('reviewed_at',2**62),
    ('evidence_url','http://example.test/permission'),('evidence_url','https://user:secret@example.test'),
    ('evidence_url','https://['),('reason','short'),('acknowledge_responsibility',False),
    ('free_access_confirmed',False),('confirm_risk_twice',False),('authorization_basis','responsibility_only'),
    ('unrecognized_permission',True)])
def test_restored_review_must_obey_the_same_writer_contract(rights,field,value):
    record=synthetic_review('free_only');record[field]=value
    rights.write_text(json.dumps({'madmom':record}))
    with pytest.raises(policy.LicenseDenied):policy.evaluate_model('madmom')


def test_restored_noncommercial_context_requires_global_commercial_off(rights):
    record=synthetic_review('free_only');record['authorization_basis']='noncommercial_context'
    rights.write_text(json.dumps({'madmom':record}))
    with pytest.raises(policy.LicenseDenied,match='entire commercial service'):policy.evaluate_model('madmom')
    rights.with_name('commercial-service.json').write_text('{"enabled":false}')
    assert not policy.evaluate_model('madmom').billable


def test_malformed_single_review_is_visible_as_unavailable_in_catalog(rights):
    rights.write_text('{"madmom":null}')
    item=next(row for row in policy.catalog() if row['id']=='madmom')
    assert not item['available_in_current_regime'] and item['effective_mode']=='disabled'


@pytest.mark.parametrize('entry,model',[
    ('btc','btc-hcqt'),('chordformer','chordformer'),('madmom','madmom'),('mega53','mvsep-mega53'),
    ('ace-launch','ace-step'),('ace-desktop','ace-step'),('ace-smoke','ace-step')])
@pytest.mark.parametrize('override',[{'mode':'disabled'},{'mode':'free_only'}])
def test_legacy_entries_refuse_before_files_runtime_or_processes(rights,tmp_path,monkeypatch,entry,model,override):
    rights.write_text(json.dumps({model:override}))
    no_process=Mock(side_effect=AssertionError('Denied model created a process'))
    monkeypatch.setattr(subprocess,'Popen',no_process)
    with pytest.raises(policy.LicenseDenied):
        if entry in ('btc','chordformer'):
            from app import chord_ml
            (chord_ml.extract_btc_hcqt if entry=='btc' else chord_ml.extract_chordformer)(tmp_path/'absent')
        elif entry=='madmom':
            from app.music_text import _madmom_processor
            _madmom_processor('madmom-deep-chroma')
        elif entry=='mega53':
            from app.mega53_runtime import infer
            infer(tmp_path/'absent',tmp_path/'out')
        elif entry=='ace-launch':
            from app.ace_step_local import launch
            launch('/absent',model_dir=str(tmp_path/'out'),confirm_download=True)
        elif entry=='ace-desktop':
            from app.ace_step_desktop_manager import start_server
            start_server(confirmed_model_download=True)
        else:
            from app.ace_step_live_smoke import test_live_inference
            test_live_inference()
    no_process.assert_not_called();assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('when',['before','during'])
def test_guarded_loaded_callback_rejects_revocation_without_second_inference(rights,when):
    rights.write_text(json.dumps({'madmom':synthetic_review('free_only')}));calls=[]
    def infer():
        calls.append(True);rights.write_text('{"madmom":{"mode":"disabled"}}');return 'unreleased'
    if when=='before':rights.write_text('{"madmom":{"mode":"disabled"}}')
    with pytest.raises(policy.LicenseDenied):policy.guarded_model_call('madmom',infer)
    assert calls==([] if when=='before' else [True])


@pytest.mark.parametrize('script,args,model',[
    ('app/ace_step_local.py',['--executable','/missing','--model-dir','MODEL','--allow-model-download'],'ace-step'),
    ('scripts/ace_gpu_benchmark.py',['--output-dir','OUTPUT'],'ace-step'),
    ('scripts/run_mrmt3_resumable.py',['--audio','AUDIO','--model','MODEL','--output','OUTPUT'],'mr-mt3-assets')])
def test_actual_standalone_diagnostic_refuses_disabled_model_before_optional_imports(tmp_path,script,args,model):
    policy_dir=tmp_path/'.studio-models';policy_dir.mkdir()
    (policy_dir/'license-policy.json').write_text(json.dumps({model:{'mode':'disabled'}}))
    values={'MODEL':str(tmp_path/'model.safetensors'),'OUTPUT':str(tmp_path/'out'),'AUDIO':str(tmp_path/'audio.wav')}
    result=subprocess.run([sys.executable,str(ROOT/script),*[values.get(x,x) for x in args]],
        cwd=tmp_path,env={**os.environ,'MTA_DATA_DIR':str(tmp_path)},capture_output=True,text=True,timeout=20,check=False)
    assert result.returncode!=0 and 'Model disabled pending license review' in result.stderr,result.stderr
    assert 'ModuleNotFoundError' not in result.stderr and not (tmp_path/'out').exists()


@pytest.mark.parametrize('model',['btc-hcqt','chordformer'])
@pytest.mark.parametrize('when',['allowed','before','during'])
def test_chord_entries_use_actual_fixed_python_child_and_reject_revocation(rights,tmp_path,monkeypatch,model,when):
    from app import chord_ml
    rights.write_text(json.dumps({model:synthetic_review('free_only')}))
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    folder=chord_ml.model_dir(model);folder.mkdir(parents=True)
    (folder/'.mta-installed.json').write_text('{}')
    child=folder/('hcqt_eval.py' if model=='btc-hcqt' else 'chord_recognition.py')
    marker=tmp_path/'executed'
    code='import pathlib,sys\npathlib.Path('+repr(str(marker))+').write_text("executed")\n'
    if when=='during':code+='pathlib.Path('+repr(str(rights))+').write_text('+repr(json.dumps({model:{'mode':'disabled'}}))+')\n'
    code+=('out=pathlib.Path(sys.argv[-1])/"fixture.lab"\n' if model=='btc-hcqt' else 'out=pathlib.Path(sys.argv[2])\n')
    code+='out.write_text("0 1 C:maj\\n")\n';child.write_text(code)
    def available(_):
        if when=='before':rights.write_text(json.dumps({model:{'mode':'disabled'}}))
        return True
    monkeypatch.setattr(chord_ml,'engine_available',available)
    fn=chord_ml.extract_btc_hcqt if model=='btc-hcqt' else chord_ml.extract_chordformer
    if when=='allowed':assert fn(tmp_path/'own-source.wav')[0].chord=='C'
    else:
        with pytest.raises(policy.LicenseDenied):fn(tmp_path/'own-source.wav')
    assert marker.exists()==(when!='before')


@pytest.mark.parametrize('engine',['madmom-deep-chroma','madmom-cnn-crf'])
@pytest.mark.parametrize('when',['allowed','before','during'])
def test_cached_madmom_processor_rechecks_current_permission(rights,monkeypatch,engine,when):
    from app import music_text
    rights.write_text(json.dumps({'madmom':synthetic_review('free_only')}));calls=[]
    class Pipeline:
        def __init__(self,items):pass
        def __call__(self,audio):
            calls.append(audio)
            if when=='during':rights.write_text('{"madmom":{"mode":"disabled"}}')
            return 'own-result'
    monkeypatch.setattr(music_text,'native_ai_device',lambda:'cpu')
    modules={'madmom_infer':SimpleNamespace(),'madmom_infer.audio':SimpleNamespace(),
        'madmom_infer.features':SimpleNamespace(),
        'madmom_infer.audio.chroma':SimpleNamespace(DeepChromaProcessor=lambda **kw:object()),
        'madmom_infer.features.chords':SimpleNamespace(DeepChromaChordRecognitionProcessor=lambda:object(),
            CNNChordFeatureProcessor=lambda **kw:object(),CRFChordRecognitionProcessor=lambda:object()),
        'madmom_infer.processors':SimpleNamespace(SequentialProcessor=Pipeline)}
    for name,module in modules.items():monkeypatch.setitem(sys.modules,name,module)
    processor,device=music_text._madmom_processor(engine)
    assert device=='cpu'
    if when=='before':rights.write_text('{"madmom":{"mode":"disabled"}}')
    if when=='allowed':assert processor('own-source')=='own-result'
    else:
        with pytest.raises(policy.LicenseDenied):processor('own-source')
    assert calls==([] if when=='before' else ['own-source'])


@pytest.mark.parametrize('when',['allowed','during'])
def test_profiled_callback_cannot_reuse_permission_after_profile_callback(rights,tmp_path,monkeypatch,when):
    from app import ai_profiled_backend as backend
    rights.write_text(json.dumps({'demucs':synthetic_review('free_only')}));called=[]
    def profile(folder,task,call):
        if when=='during':rights.write_text('{"demucs":{"mode":"disabled"}}')
        return call()
    monkeypatch.setattr(backend,'profile_call',profile)
    monkeypatch.setattr(backend.runpy,'run_module',lambda *a,**kw:called.append(True))
    monkeypatch.setattr(sys,'argv',['profile','--backend','demucs','--task-id','own',
        '--report-dir',str(tmp_path/'out'),'--','-n','htdemucs','own.wav'])
    if when=='allowed':backend.main()
    else:
        with pytest.raises(policy.LicenseDenied):backend.main()
    assert called==([True] if when=='allowed' else [])


@pytest.mark.parametrize('when',['allowed','before','during'])
def test_mega53_fixed_child_cannot_publish_after_permission_revocation(rights,tmp_path,monkeypatch,when):
    from app import mega53_runtime as mega
    rights.write_text(json.dumps({'mvsep-mega53':synthetic_review('free_only')}))
    folder=tmp_path/'upstream';folder.mkdir();source=tmp_path/'own.wav';source.write_bytes(b'own-input')
    config=tmp_path/'own.yaml';config.write_text('own-generated-config');weights=tmp_path/'own.ckpt';weights.write_bytes(b'own')
    marker=tmp_path/'executed'
    code='import pathlib,sys,wave\npathlib.Path('+repr(str(marker))+').write_text("executed")\n'
    if when=='during':code+='pathlib.Path('+repr(str(rights))+').write_text(\'{"mvsep-mega53":{"mode":"disabled"}}\')\n'
    code+='out=pathlib.Path(sys.argv[sys.argv.index("--store_dir")+1]);out.mkdir(exist_ok=True)\nfor name in ("lead-vocal","back-vocal"):\n with wave.open(str(out/(name+".wav")),"wb") as w:w.setparams((1,2,44100,0,"NONE",""));w.writeframes(b"\\0\\0"*10)\n'
    (folder/'inference.py').write_text(code)
    for name,value in [('ROOT',folder),('CONFIG',config),('CHECKPOINT',weights),('PYTHON',Path(sys.executable))]:monkeypatch.setenv('MTA_MEGA53_'+name,str(value))
    original=mega._verified_file
    monkeypatch.setattr(mega,'_verified_file',lambda path,label:Path(path) if label=='Python interpreter' else original(path,label))
    def checked(path):
        if when=='before':rights.write_text('{"mvsep-mega53":{"mode":"disabled"}}')
        return weights
    monkeypatch.setattr(mega,'verify_mega53_checkpoint',checked)
    if when=='allowed':
        lead,backing,_=mega.infer(source,tmp_path/'out');assert lead.is_file() and backing.is_file()
    else:
        with pytest.raises(policy.LicenseDenied):mega.infer(source,tmp_path/'out')
        assert not list((tmp_path/'out').glob('*.wav'))
    assert marker.exists()==(when!='before')


@pytest.mark.parametrize('revoke',[False,True,'decode'])
def test_resumable_mrmt3_rechecks_each_actual_forward_before_saving_windows(rights,tmp_path,monkeypatch,revoke):
    import wave
    import numpy as np
    from app import mrmt3_decode
    rights.write_text(json.dumps({'mr-mt3-assets':synthetic_review('free_only')}))
    audio=tmp_path/'own.wav';weights=tmp_path/'weights/model.safetensors';weights.parent.mkdir();weights.write_bytes(b'own-fixture')
    with wave.open(str(audio),'wb') as w:w.setparams((1,2,16000,0,'NONE',''));w.writeframes(b'\0\0'*1600)
    calls=[]
    class Network:
        def load_state_dict(self,*a,**kw):pass
        def to(self,*a):return self
        def eval(self):return self
    class Model:
        model_config={};codec='own-fixture'
        def _initialize_vocab(self):pass
        def preprocess(self,*a):return {'inputs':np.zeros((2,1))}
        def forward(self,value):
            calls.append(True)
            if revoke is True:rights.write_text('{"mr-mt3-assets":{"mode":"disabled"}}')
            return {'tokens':[[1,2]],'frame_times':[[0.0]]}
    torch=SimpleNamespace(set_num_threads=lambda n:None,cuda=SimpleNamespace(is_available=lambda:False),inference_mode=nullcontext)
    modules={'torch':torch,'transformers':SimpleNamespace(T5Config=SimpleNamespace(from_dict=lambda x:x)),
        'safetensors':SimpleNamespace(),'safetensors.torch':SimpleNamespace(load=lambda *a,**kw:{}),
        'mt3_infer':SimpleNamespace(),'mt3_infer.adapters':SimpleNamespace(),
        'mt3_infer.adapters.mr_mt3':SimpleNamespace(MRMT3Adapter=Model,_import_t5_model=lambda:lambda cfg:Network())}
    for name,module in modules.items():monkeypatch.setitem(sys.modules,name,module)
    # This test exercises per-forward revocation with an injected model, not
    # runtime identity. Unmocked CLI/API preflight is covered separately.
    from app import mrmt3_adapter,transcription_source_contract
    files={'weights/model.safetensors':hashlib.sha256(weights.read_bytes()).hexdigest()}
    monkeypatch.setattr(mrmt3_adapter,'verified_runtime',lambda:(tmp_path,{'files':files},sys.executable))
    monkeypatch.setattr(transcription_source_contract,'imports',lambda *a:nullcontext())
    monkeypatch.setattr(transcription_source_contract,'checkpoint_bytes',lambda *a:(weights,weights.read_bytes()))
    def decode(*args):
        if revoke=='decode':rights.write_text('{"mr-mt3-assets":{"mode":"disabled"}}')
        return [],{'own_fixture':True}
    monkeypatch.setattr(mrmt3_decode,'decode',decode)
    spec=importlib.util.spec_from_file_location('own_resumable',ROOT/'scripts/run_mrmt3_resumable.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    args=['--audio',str(audio),'--model',str(weights),'--output',str(tmp_path/'out')]
    if revoke:
        with pytest.raises(policy.LicenseDenied):module.main(args)
        assert calls==([True] if revoke is True else [True,True])
        assert len(list((tmp_path/'out').glob('window-*.json')))==(0 if revoke is True else 2)
        assert not (tmp_path/'out/prediction.json').exists()
    else:
        assert module.main(args)==0 and calls==[True,True]
        assert len(list((tmp_path/'out').glob('window-*.json')))==2 and (tmp_path/'out/prediction.json').is_file()
