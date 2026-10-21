"""Orchestration/rights transport tests with explicitly synthetic worker results."""
import io
import wave
import zipfile
import pytest
from app.studio_multitrack import transcribe_separated
from app.studio_compute import stem_artifacts
from app.music_interchange import MusicResult,MusicPart
from app.models import MidiNote


def music(name):
    return MusicResult(parts=[MusicPart(id='p',name=name,program=0,notes=[MidiNote(id='n',pitch=60,start_ms=0,duration_ms=500)])])


def test_deep_executes_separation_and_seven_real_backend_requests():
    calls=[];ack=[]
    def compute(user,kind,plan,**kwargs):
        calls.append((user,kind,plan,kwargs))
        result=({f'stem_{label}.wav':label.encode() for label in ['bass','drums','other','vocals']}
                if kind=='demucs' else music(kind))
        return result,{'usage':{'cpu_seconds':2.,'gpu_seconds':1.},'acknowledge':lambda:ack.append(kind)}
    result,meta=transcribe_separated(7,b'input',{},cancelled=lambda:False,timeout=100,compute=compute)
    assert len(calls)==8 and calls[0][1]=='demucs'
    assert sum(kind.endswith('yourmt3') for _,kind,_,_ in calls)==4
    assert sum(kind.endswith('basic-pitch') for _,kind,_,_ in calls)==3
    assert not any(k.endswith('basic-pitch') and v['audio']==b'drums' for _,k,_,v in calls)
    assert len(result.parts)==4 and len({p.id for p in result.parts})==4
    assert meta['usage']=={'cpu_seconds':16.,'gpu_seconds':8.}
    assert all(p.program==0 for p in result.parts) # same GM across separate sources preserved
    assert not ack
    meta['acknowledge']();assert len(ack)==8


def test_deep_cancellation_and_worker_failure_are_not_hidden():
    with pytest.raises(RuntimeError,match='cancelled'):
        transcribe_separated(1,b'',{},cancelled=lambda:True,timeout=10,compute=lambda *a,**k:pytest.fail('must not execute'))
    def fail(*a,**k):raise RuntimeError('real model missing')
    with pytest.raises(RuntimeError,match='real model missing'):
        transcribe_separated(1,b'',{},cancelled=lambda:False,timeout=10,compute=fail)


def wav():
    target=io.BytesIO()
    with wave.open(target,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(b'\0\0'*100)
    return target.getvalue()


def bundle(extra=None):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as archive:
        for label in ('bass','drums','other','vocals'):archive.writestr('stem_'+label+'.wav',wav())
        if extra:archive.writestr(extra,b'invalid')
    return out.getvalue()


def test_separated_transport_validates_wav_and_expected_names():
    assert len(stem_artifacts(bundle()))==4
    for name in ('../evil.wav','arbitrary.wav'):
        with pytest.raises(ValueError,match='exactly'):stem_artifacts(bundle(name))


def test_deep_admission_propagates_free_only_component(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.studio_jobs import register_routes
    from app.models import Project,Track
    from app import model_license_policy as policy
    from app import ai_worker_registry
    monkeypatch.delenv('MTA_NATIVE_SINGLE_USER',raising=False)
    monkeypatch.delenv('MTA_STUDIO_TRANSCRIBER',raising=False)
    monkeypatch.setattr(ai_worker_registry,'resolve_worker',lambda kind:'installed')
    project=Project(id='fixture',title='Fixture',target='DAW_MIDI',project_kind_version=1,tracks=[Track(id='source',name='Mix',filename='mix.wav',kind='audio')])
    def evaluate(kind,plan):
        return policy.Decision(kind,'free_only' if kind=='demucs' else 'cost_recovery','https://example.com','a'*64)
    monkeypatch.setattr(policy,'evaluate',evaluate)
    app=FastAPI();register_routes(app,lambda request,pid:project,lambda request:{'id':7,'role':'user'},lambda *a:None)
    response=TestClient(app).post('/api/projects/fixture/ai-studio/jobs',json={
        'operation':'audio-to-midi','mode':'maximum','track_ids':['source'],'end_ms':1000})
    assert response.status_code==422 and 'Free-only' in response.text
