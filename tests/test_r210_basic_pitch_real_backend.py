"""Opt-in real ONNX inference through the global queue and CPU ledger."""
import io
import json
import os
import secrets
from pathlib import Path
import zipfile

import numpy as np
import pytest
import soundfile as sf


@pytest.mark.skipif(not os.getenv('MTA_STUDIO_PYTHON'), reason='Requires the separate reviewed Basic Pitch ONNX runtime')
def test_real_basic_pitch_global_queue_cpu_and_artifacts(tmp_path, monkeypatch):
    from app import auth, ai_arranger_runtime as queue, ai_metering_agent as agent, ai_billing
    from app.music_interchange import MusicResult
    root = Path(__file__).resolve().parents[1]
    registry = tmp_path/'registry.json'
    registry.write_text('[]')
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_EXECUTABLE',str(root/'app/ai_studio_adapter.py'))
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_PYTHON',os.environ['MTA_STUDIO_PYTHON'])
    monkeypatch.setattr(auth, 'data_root', lambda: tmp_path/'data')
    monkeypatch.setattr(queue, '_ROOT', tmp_path/'jobs')
    monkeypatch.setenv('MTA_AI_ENGINE_REGISTRY_FILE', str(registry))
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path/'worker-data'))
    monkeypatch.setenv('OPENBLAS_NUM_THREADS', '1')
    monkeypatch.setenv('OMP_NUM_THREADS', '1')
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    monkeypatch.setenv('MTA_ADMIN_PASSWORD', secrets.token_urlsafe(32))
    auth.init_auth_db()
    uid = auth.find_user('admin')['id']
    rate = 44100
    waveform = np.zeros(rate*5, dtype=np.float32)
    expected = [60, 64, 67, 72]
    for index, pitch in enumerate(expected):
        t = np.arange(round(.7*rate))/rate
        envelope = np.minimum(t/.01,1)*np.exp(-t*2)
        tone = sum(np.sin(2*np.pi*440*2**((pitch-69)/12)*h*t)/h**1.5 for h in range(1,5))*.16*envelope
        start = round((index+.25)*rate)
        waveform[start:start+len(tone)] = tone
    source = io.BytesIO()
    sf.write(source, waveform, rate, format='WAV', subtype='PCM_16')
    payload, metadata = agent.execute_registered_worker(uid, 'audio-to-midi', {'kind':'audio-to-midi',
        'options':{'name':'Synthetic reference melody', 'program':0}}, source_wav=source.getvalue(), timeout_seconds=180)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        result = MusicResult.model_validate_json(archive.read('music.json'))
    with ai_billing.db() as con:
        ledger = dict(con.execute('SELECT queue_job_id,status,usage_json,resource_source FROM ai_compute_jobs WHERE id=?',
                                  (metadata['job_id'],)).fetchone())
    state = queue.get(ledger['queue_job_id'])
    assert state['state'] == 'completed'
    assert metadata['usage']['cpu_seconds'] > 0
    assert not metadata['gpu_metered'] and 'gpu_seconds' not in metadata['usage']
    assert json.loads(ledger['usage_json'])['cpu_seconds'] == metadata['usage']['cpu_seconds']
    assert state['cpu_seconds'] == metadata['usage']['cpu_seconds']
    notes = result.parts[0].notes
    assert len(result.parts) == 1
    matched = sum(any(n.pitch == pitch and abs(n.start_ms-(i+.25)*1000) <= 50 for n in notes)
                  for i,pitch in enumerate(expected))
    assert matched == 4, [n.model_dump() for n in notes]
    assert all(n.origin == 'predicted' and n.confidence is None for n in notes)
    precision = matched/len(notes)
    recall = matched/len(expected)
    report = {'fixture':'5-second synthetic harmonic melody; not a real-song accuracy benchmark',
              'model':'basic-pitch-0.4.0-onnx', 'device':'CPU only', 'expected_pitches':expected,
              'predicted_notes':[n.model_dump() for n in notes], 'matched_onsets_50ms':matched,
              'precision_on_fixture':precision, 'recall_on_fixture':recall,
              'f1_on_fixture':2*precision*recall/(precision+recall), 'usage':metadata['usage'],
              'queue_state':state['state'], 'ledger_status':ledger['status'], 'resource_source':ledger['resource_source']}
    if os.getenv('MTA_STUDIO_VALIDATION_REPORT'):
        Path(os.environ['MTA_STUDIO_VALIDATION_REPORT']).write_text(json.dumps(report,indent=2))


@pytest.mark.skipif(not os.getenv('MTA_STUDIO_PYTHON'), reason='Requires the reviewed Basic Pitch ONNX runtime')
def test_real_project_two_sources_then_vocal_harmony(tmp_path,monkeypatch):
    import time
    from fastapi.testclient import TestClient
    from starlette.requests import Request
    from app import auth,storage,ai_arranger_runtime as queue
    from app.models import Track,Clip
    from app.main import app
    root=Path(__file__).resolve().parents[1]
    registry=tmp_path/'registry.json'
    registry.write_text('[]')
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_EXECUTABLE',str(root/'app/ai_studio_adapter.py'))
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_PYTHON',os.environ['MTA_STUDIO_PYTHON'])
    monkeypatch.setattr(auth,'data_root',lambda:tmp_path/'data')
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects');storage.ROOT.mkdir()
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'jobs')
    for key,value in {'MTA_AI_ENGINE_REGISTRY_FILE':str(registry),'MTA_AI_WORKER_ENABLED':'true',
        'MTA_DATA_DIR':str(tmp_path/'worker'),'MTA_NATIVE_SINGLE_USER':'false','MTA_ALLOW_INSECURE_NO_AUTH':'false',
        'MTA_ADMIN_PASSWORD':secrets.token_urlsafe(32),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','ORT_DISABLE_TELEMETRY':'1'}.items():monkeypatch.setenv(key,value)
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT',raising=False)
    auth.init_auth_db();uid=auth.find_user('admin')['id']
    project=storage.create_project('Real two-source roundtrip',target='DAW_MIDI',owner_user_id=uid)
    rate=44100;t=np.arange(rate*2)/rate
    for index,pitch in enumerate((69,72)):
        name=f'source-{index}.wav';sf.write(storage.audio_path(project.id,name),.2*np.sin(2*np.pi*440*2**((pitch-69)/12)*t),rate)
        project.tracks.append(Track(id=f's{index}',name=f'Input {index}',filename=name,duration_ms=2000,
            delay_ms=500,clips_initialized=True,clips=[Clip(id=f'c{index}',source_end_ms=2000)]))
    storage.save_project(project)
    client=TestClient(app);client.headers['user-agent']='testclient'
    cookie=auth.create_session(uid,Request({'type':'http','headers':[(b'user-agent',b'testclient')]}))
    client.cookies.set('mta_session',cookie)
    def run(body):
        response=client.post(f'/api/projects/{project.id}/ai-studio/jobs',json=body,headers={'X-MTA-Request':'1'})
        assert response.status_code==200,response.text
        jid=response.json()['job_id'];deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            data=client.get(f'/api/projects/{project.id}/ai-studio/jobs/{jid}').json()
            if data['job']['state'] not in ('running','queued','blocked'):break
            time.sleep(.1)
        assert data['job']['state']=='completed',data
        assert data['imported'] and data['job']['cpu_seconds']>0
        with auth.db() as con:
            rows=con.execute('SELECT status,usage_json FROM ai_compute_jobs WHERE queue_job_id=?',(jid,)).fetchall()
        assert rows and all(r['status']=='done' for r in rows)
        total=sum(json.loads(r['usage_json'])['cpu_seconds'] for r in rows)
        assert abs(total-data['job']['cpu_seconds'])<.001
        assert data['job']['gpu_seconds'] is None
        return jid
    transcription=run({'operation':'audio-to-midi','track_ids':['s0','s1'],'start_ms':500,'end_ms':2500})
    reopened=storage.load_project(project.id)
    generated=[t for t in reopened.tracks if t.music_result_id==transcription]
    assert len(generated)==2 and all(t.kind=='midi' and t.midi_notes for t in generated)
    assert all(min(n.start_ms for n in t.midi_notes)>=500 for t in generated)
    harmony=run({'operation':'vocal-harmony','track_ids':[generated[0].id],'start_ms':500,'end_ms':2500,
        'settings':{'voices':4,'retain_melody':False}})
    reopened=storage.load_project(project.id)
    assert len([t for t in reopened.tracks if t.music_result_id==harmony])==4
    assert all(storage.audio_path(project.id,t.filename).is_file() for t in reopened.tracks)
    assert len(reopened.music_imports)==2
