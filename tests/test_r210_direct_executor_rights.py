"""Actual local rights policy at direct Python/CLI boundaries; no model grant."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from app import model_license_policy as policy

ENTRIES={
    'whisper':'whisper','whisper_progressive':'whisper','loaded_whisper':'whisper',
    'basic_pitch':'basic-pitch','studio':'basic-pitch','yourmt3':'yourmt3',
    'mrmt3':'mr-mt3-assets','mrmt3_selftest':'mr-mt3-assets','transkun':'transkun-assets',
    'transkun_cli':'transkun-assets','drumsep':'drumsep-weights','sam_cli':'sam-audio',
    'profile_demucs':'demucs','profile_sam':'sam-audio','oddvoices':'oddvoices',
    'singer_bridge':'diffsinger-nishiren','singer_onnx':'diffsinger-nishiren',
    'singer_session':'diffsinger-nishiren',
}


def dispatch(entry,folder,monkeypatch):
    source=folder/'missing.wav';out=folder/'absent'/'result.wav'
    if entry=='whisper':
        from app.music_text import extract_lyrics
        return extract_lyrics(source)
    if entry=='whisper_progressive':
        from app.music_text import extract_lyrics_progressive
        return extract_lyrics_progressive(source)
    if entry=='loaded_whisper':
        from app.music_text import _whisper_transcribe
        class Model:
            def float(self):pytest.fail('Disabled loaded model touched')
            def transcribe(self,*a,**kw):pytest.fail('Disabled cached model inferred')
        return _whisper_transcribe(Model(),str(source),language=None,device='cpu')
    if entry in {'basic_pitch','studio'}:
        from app import ai_studio_adapter
        if entry=='basic_pitch':return ai_studio_adapter.transcribe(source,{})
        return ai_studio_adapter.infer({'kind':'audio-to-midi-basic-pitch','source_audio':str(source)},out)
    if entry=='yourmt3':
        from app.yourmt3_adapter import transcribe
        return transcribe(source,{})
    if entry in {'mrmt3','mrmt3_selftest'}:
        from app.mrmt3_adapter import transcribe,_transcribe
        return _transcribe(source,{},_require_tested=False) if entry.endswith('selftest') else transcribe(source,{})
    if entry=='transkun':
        from app.transkun_adapter import transcribe
        return transcribe(source,{'asset_id':'missing-asset'})
    if entry=='drumsep':
        from app.drumsep_onnx_worker import infer
        return infer(source,folder/'missing.onnx',out)
    if entry=='oddvoices':
        from app.vocal_synthesis import render
        return render(None,{},out)
    if entry in {'singer_bridge','singer_onnx','singer_session'}:
        from app import diffsinger_bridge,diffsinger_onnx
        if entry=='singer_bridge':return diffsinger_bridge.run(source,out)
        if entry=='singer_onnx':return diffsinger_onnx.run(source,out)
        return diffsinger_onnx.session(source,'0'*64)
    if entry=='sam_cli':
        from app.sam_audio_worker import main
        args=['worker','--source',str(source),'--output',str(out),'--model','facebook/sam-audio-small','--prompt','voice']
    elif entry.startswith('profile_'):
        from app.ai_profiled_backend import main
        args=['worker','--backend','demucs' if entry.endswith('demucs') else 'sam-audio',
              '--task-id','fixture','--report-dir',str(out.parent),'--',str(source)]
    else:
        from app.transkun_runner import main
        args=['worker',*(arg for key in ('source','output','checkpoint','checkpoint-sha256','config','config-sha256','runtime','device')
                         for arg in ('--'+key,str(source)))]
    monkeypatch.setattr(sys,'argv',args)
    return main()


@pytest.fixture
def rights(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    path=tmp_path/'license-policy.json'
    monkeypatch.setattr(policy,'_path',lambda:path)
    monkeypatch.setenv('MTA_LYRICS_MODEL_DIR',str(tmp_path/'whisper-cache'))
    monkeypatch.setenv('MTA_NEURAL_SINGER_POLICY_MODEL','diffsinger-nishiren')
    monkeypatch.setenv('MTA_DIFFSINGER_VOCODER_POLICY_MODEL','diffsinger-vocoder')
    return path


@pytest.mark.parametrize('entry',ENTRIES)
@pytest.mark.parametrize('denial',['disabled','commercial_free_only','commercial_off','corrupt'])
def test_direct_boundary_rechecks_actual_rights_before_source_model_or_output_effects(rights,tmp_path,monkeypatch,entry,denial):
    model=ENTRIES[entry]
    # Synthetic permissions for OTHER components, not a real checkpoint grant.
    value={name:{'mode':'cost_recovery'} for name in {'diffsinger-nishiren','diffsinger-vocoder'}}
    value[model]={'mode':'free_only' if denial=='commercial_free_only' else 'cost_recovery' if denial=='commercial_off' else 'disabled'}
    rights.write_text('{' if denial=='corrupt' else json.dumps(value))
    if denial=='commercial_free_only':
        from app import auth
        from app.regime_operation_fence import initialize
        (tmp_path/'service-regime.json').write_text('{"regime":"COMMERCIAL","revision":0}')
        with auth.db() as c:
            c.execute('BEGIN IMMEDIATE')
            initialize(c,initial_regime='COMMERCIAL')
    if denial=='commercial_off':(tmp_path/'commercial-service.json').write_text('{"enabled":false}')
    with pytest.raises((policy.LicenseDenied,json.JSONDecodeError)):
        dispatch(entry,tmp_path,monkeypatch)
    assert not (tmp_path/'absent').exists() and not (tmp_path/'whisper-cache').exists()


def test_loaded_whisper_revocation_denies_mps_cpu_fallback(rights,tmp_path):
    from app.music_text import _whisper_transcribe
    rights.write_text('{}');calls=[]
    class Model:
        def float(self):return self
        def to(self,device):pytest.fail('Revoked model must not migrate to CPU')
        def transcribe(self,*a,**kw):
            calls.append(kw)
            rights.write_text('{"whisper":{"mode":"disabled"}}')
            raise RuntimeError('MPS float64')
    with pytest.raises(policy.LicenseDenied):_whisper_transcribe(Model(),'unused.wav',language=None,device='mps')
    assert len(calls)==1


def test_permitted_loaded_whisper_retains_original_fallback_and_timestamps(rights):
    from app.music_text import _whisper_transcribe
    rights.write_text('{}');calls=[];result={'segments':[{'start':0.,'end':1.,'text':'fixture'}]}
    class Model:
        def float(self):return self
        def to(self,device):calls.append(('to',device));return self
        def transcribe(self,*a,**kw):
            calls.append(('infer',kw['fp16']))
            if len(calls)==1:raise RuntimeError('MPS float64')
            return result
    assert _whisper_transcribe(Model(),'unused.wav',language=None,device='mps') is result
    assert calls==[('infer',False),('to','cpu'),('infer',False)]


@pytest.mark.parametrize('entry',['singer_bridge','singer_onnx','singer_session'])
def test_acoustic_permission_cannot_replace_separate_vocoder_permission(rights,tmp_path,monkeypatch,entry):
    rights.write_text('{"diffsinger-nishiren":{"mode":"cost_recovery"},"diffsinger-vocoder":{"mode":"disabled"}}')
    with pytest.raises(policy.LicenseDenied,match='diffsinger-vocoder'):
        dispatch(entry,tmp_path,monkeypatch)


def test_singing_component_policy_cannot_be_bypassed_by_allowed_singer_and_vocoder(rights,tmp_path,monkeypatch):
    from app import diffsinger_onnx
    rights.write_text(json.dumps({model:{'mode':'cost_recovery'} for model in ('diffsinger-nishiren','diffsinger-vocoder')}))
    monkeypatch.setattr(diffsinger_onnx,'inventory',lambda:({'bindings':{},'licenses':[{'policy_model':'unreviewed-engine'}]},None))
    with pytest.raises(policy.LicenseDenied,match='unreviewed-engine'):
        diffsinger_onnx.run(tmp_path/'missing',tmp_path/'output')
    assert not (tmp_path/'output').exists()


@pytest.mark.parametrize('kind',['sam','demucs','drumsep','transkun'])
def test_independent_actual_cli_denies_before_optional_runtime_import(tmp_path,kind):
    root=Path(__file__).resolve().parents[1]
    folder=tmp_path/'.studio-models';folder.mkdir()
    model={'sam':'sam-audio','demucs':'demucs','drumsep':'drumsep-weights','transkun':'transkun-assets'}[kind]
    (folder/'license-policy.json').write_text(json.dumps({model:{'mode':'disabled'}}))
    source=str(tmp_path/'missing.wav');output=str(tmp_path/'result')
    if kind=='sam':args=['sam_audio_worker.py','--source',source,'--output',output,'--model','facebook/sam-audio-small','--prompt','voice']
    elif kind=='demucs':args=['ai_profiled_backend.py','--backend','demucs','--task-id','fixture','--report-dir',output,'--',source]
    elif kind=='drumsep':args=['drumsep_onnx_worker.py','--source',source,'--model',source,'--output',output]
    else:args=['transkun_runner.py',*(arg for key in ('source','output','checkpoint','checkpoint-sha256','config','config-sha256','runtime','device') for arg in ('--'+key,source))]
    env={**os.environ,'MTA_DATA_DIR':str(tmp_path)}
    result=subprocess.run([sys.executable,str(root/'app'/args[0]),*args[1:]],cwd=tmp_path,env=env,
                          capture_output=True,text=True,timeout=20,check=False)
    assert result.returncode!=0 and 'Model disabled pending license review' in result.stderr,result.stderr
    assert 'ModuleNotFoundError' not in result.stderr and not Path(output).exists()


@pytest.mark.parametrize('mode',['disabled','cost_recovery'])
def test_model_only_interpreter_reads_current_policy_without_web_dependencies(tmp_path,mode):
    folder=tmp_path/'.studio-models';folder.mkdir()
    (folder/'license-policy.json').write_text(json.dumps({'sam-audio':{'mode':mode}}))
    root=Path(__file__).resolve().parents[1]
    # -S removes site-packages: no FastAPI,qrcode,Pydantic,Torch or SAM package.
    result=subprocess.run([sys.executable,'-S',str(root/'app/sam_audio_worker.py'),
        '--source',str(tmp_path/'missing.wav'),'--output',str(tmp_path/'output'),
        '--model','facebook/sam-audio-small','--prompt','voice'],
        env={**os.environ,'MTA_DATA_DIR':str(tmp_path)},capture_output=True,text=True,timeout=10,check=False)
    assert result.returncode!=0
    assert all(name not in result.stderr for name in ["No module named 'fastapi'","No module named 'qrcode'","No module named 'pydantic'"])
    if mode=='disabled':assert 'Model disabled pending license review' in result.stderr
    else:assert "No module named 'torch'" in result.stderr
    assert not (tmp_path/'auth.sqlite3').exists() and not (tmp_path/'output').exists()
