"""An engine permission cannot admit arbitrary checkpoint paths/repositories."""
import json
import base64
import sys
from unittest.mock import Mock

import pytest
from app import model_license_policy as policy,model_selectors as selectors
from test_r208_unified_adapter_billing_e2e import operator as operator,source_audio  # noqa: F401
from test_r210_execution_entry_acceptance import env as env,registered as registered,api  # noqa: F401


@pytest.fixture
def local(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    monkeypatch.setattr(policy,'_path',lambda:tmp_path/'policy.json')
    monkeypatch.setenv('MTA_LYRICS_MODEL_DIR',str(tmp_path/'no-cache'))
    return tmp_path


@pytest.mark.parametrize('model',['/untrusted/unknown.pt','./tiny.pt','https://example.test/a.pt','tiny/../weights',
                                 '--model=base','unreviewed',{'path':'tiny.pt'},1,False])
def test_whisper_unknown_checkpoint_never_probes_runtime_or_creates_cache(local,monkeypatch,model):
    from app import music_text
    probe=Mock(side_effect=AssertionError('Runtime must not be probed'))
    monkeypatch.setattr(music_text.importlib.util,'find_spec',probe)
    with pytest.raises(ValueError):music_text.extract_lyrics(local/'missing.wav',model_name=model)
    probe.assert_not_called();assert not (local/'no-cache').exists()


@pytest.mark.parametrize('model',['/untrusted/checkpoint','other/sam-audio-small','facebook/sam-audio-small@unreviewed',
                                 'facebook/sam-audio-small/../other','https://example.test/sam','--model=x'])
def test_actual_sam_entry_rejects_unknown_identity_before_heavy_import(local,monkeypatch,model):
    from app import sam_audio_worker
    import builtins
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name in {'torch','torchaudio','sam_audio'}:pytest.fail('Unknown checkpoint reached optional runtime')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    monkeypatch.setattr(sys,'argv',['sam','--source','missing','--output',str(local/'out'),
                                  '--model='+model,'--prompt','voice'])
    with pytest.raises(ValueError):sam_audio_worker.main()
    assert not (local/'out').exists()


@pytest.mark.parametrize('kind,model',[('whisper','/untrusted/unknown.pt'),('sam-audio','foreign/repo'),('demucs','foreign_model')])
def test_invalid_selector_is_refused_before_actual_queue_ledger_admission(operator,kind,model):
    from app import ai_metering_agent,ai_billing
    with ai_billing.db() as c:before=c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]
    with pytest.raises(ValueError):
        ai_metering_agent.execute_registered_worker(operator,kind,{'model':model},source_wav=source_audio())
    with ai_billing.db() as c:assert c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]==before


@pytest.mark.parametrize('kind,model',[('whisper','tiny.en'),('sam-audio','sam-audio-small'),('demucs','htdemucs_6s')])
def test_published_selectors_retain_actual_accounted_worker_contract(operator,kind,model):
    from app import ai_metering_agent,ai_billing
    data,metadata=ai_metering_agent.execute_registered_worker(operator,kind,{'model':model},source_wav=source_audio())
    assert data and metadata['usage']['cpu_seconds']>=0
    with ai_billing.db() as c:
        row=c.execute('SELECT status,kind FROM ai_compute_jobs WHERE id=?',(metadata['job_id'],)).fetchone()
        assert tuple(row)==('done',kind)


@pytest.mark.parametrize('kind,variable,value',[('whisper','MTA_LYRICS_WHISPER_MODEL','/untrusted/private.pt'),
                                              ('sam-audio','MTA_AI_SAM_MODEL','foreign/repo')])
def test_environment_defaults_cannot_bypass_parent_or_direct_adapter(local,monkeypatch,kind,variable,value):
    monkeypatch.setenv(variable,value)
    with pytest.raises(ValueError):policy.evaluate(kind,{})
    from app import ai_unified_adapter
    with pytest.raises(ValueError):ai_unified_adapter.infer({'kind':kind},local/'missing'/'out.wav')
    assert not (local/'missing').exists() and not (local/'no-cache').exists()


@pytest.mark.parametrize('arguments',[['--name','foreign'],['-n','/untrusted/weights'],[],
    ['-n','htdemucs','--name','mdx'],['--nam=foreign'],['-n','htdemucs','--repo','/untrusted'],
    ['-n','htdemucs','--rep=/untrusted'],['-n','htdemucs','-r/untrusted'],['-n','htdemucs','--r','/untrusted'],
    ['--name']])
def test_profiled_demucs_refuses_ambiguous_or_repository_override_before_profiling(local,monkeypatch,arguments):
    from app import ai_profiled_backend as backend
    profile=Mock(side_effect=AssertionError('Invalid selector reached profiling'))
    monkeypatch.setattr(backend,'profile_call',profile)
    monkeypatch.setattr(sys,'argv',['profile','--backend','demucs','--task-id','fixture','--report-dir',str(local/'out'),'--',*arguments])
    with pytest.raises(ValueError):backend.main()
    profile.assert_not_called();assert not (local/'out').exists()


@pytest.mark.parametrize('arguments',[['-n','htdemucs','--device','cpu','source.wav'],
                                     ['--name=htdemucs_6s','--two-stems','vocals','source.wav'],
                                     ['-nmdx_extra','--out','output','source.wav']])
def test_profiled_demucs_preserves_valid_arguments_and_restores_process_argv(local,monkeypatch,arguments):
    from app import ai_profiled_backend as backend
    seen=[]
    monkeypatch.setattr(backend,'profile_call',lambda folder,task,callback:callback())
    monkeypatch.setattr(backend.runpy,'run_module',lambda name,run_name:seen.append((name,list(sys.argv))))
    original=['profile','--backend','demucs','--task-id','fixture','--report-dir',str(local/'out'),'--',*arguments]
    monkeypatch.setattr(sys,'argv',original)
    backend.main()
    assert seen==[('demucs.separate',['demucs',*arguments])] and sys.argv is original


def test_whisper_aliases_and_shared_demucs_registry_preserve_declared_variants(local,monkeypatch):
    from app import ai_models,model_updater
    assert {row['id'] for row in ai_models.LYRICS_MODELS}<=selectors.WHISPER_MODELS
    assert model_updater.OFFICIAL_DEMUCS_MODELS is selectors.OFFICIAL_DEMUCS_MODELS
    for name in ['tiny.en','medium.en','large','large-v3-turbo']:
        assert selectors.whisper_model(name)==name
    monkeypatch.setenv('MTA_LYRICS_WHISPER_MODEL','base.en')
    assert selectors.whisper_model(None)=='base.en'
    assert selectors.sam_model('sam-audio-small')==selectors.sam_model('facebook/sam-audio-small')


def test_unified_whisper_uses_same_validated_default_as_direct_path(local,monkeypatch):
    from app import ai_unified_adapter,music_text
    folder=local/'job';folder.mkdir();source=folder/'source.wav';source.write_bytes(b'own transport fixture')
    monkeypatch.setenv('MTA_LYRICS_WHISPER_MODEL','base.en');seen=[]
    monkeypatch.setattr(music_text,'extract_lyrics',lambda path,**kwargs:(seen.append(kwargs['model_name']) or []))
    ai_unified_adapter.infer({'kind':'whisper','source_audio':str(source)},folder/'preview.wav')
    assert seen==['base.en'] and json.loads((folder/'transcript.json').read_text())=={'lines':[]}


@pytest.mark.parametrize('transport',['json','wav'])
@pytest.mark.parametrize('kind,model',[('whisper','/untrusted/checkpoint.pt'),('sam-audio','other/private'),('demucs','custom_model')])
def test_actual_token_api_rejects_unknown_checkpoint_without_worker_or_ledger(env,registered,kind,model,transport):
    from app import ai_access,auth
    token=ai_access.issue(env,'selector rejection fixture')
    headers={'Authorization':'Bearer '+token['token']}
    with api() as client:
        if transport=='json':response=client.post('/api/ai-jobs/execute',json={'kind':kind,'plan':{'model':model}},headers=headers)
        else:
            encoded=base64.urlsafe_b64encode(json.dumps({'model':model}).encode()).decode()
            headers.update({'Content-Type':'audio/wav','X-MTA-AI-Options':encoded})
            response=client.post('/api/ai-jobs/execute-audio/'+kind,content=source_audio(),headers=headers)
    assert response.status_code==400,response.text
    assert not registered[1].exists()
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]==0
