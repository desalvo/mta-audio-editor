"""Opt-in real CPU models and publication, separate from model-less CI."""
import os
from pathlib import Path
import shutil
import time
import pytest


@pytest.mark.skipif(not os.getenv('MTA_TEST_ACCURATE_FIXTURE'),reason='Requires explicitly installed YourMT3 and Basic Pitch plus an authorized WAV fixture')
def test_real_models_reconcile_publish_alternatives_and_reopen(tmp_path,monkeypatch):
    from app.main import app
    from app import storage,ai_arranger_runtime as queue
    from app.models import Track,Clip
    from app.studio_jobs import folder
    from fastapi.testclient import TestClient
    import soundfile as sf
    import json
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true');monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true')
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects');storage.ROOT.mkdir()
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'jobs')
    source=Path(os.environ['MTA_TEST_ACCURATE_FIXTURE']);info=sf.info(source);duration=round(info.duration*1000)
    project=storage.create_project('Real accurate mode',target='DAW_MIDI')
    project.tracks=[Track(id='piano',name='Piano',filename='piano.wav',duration_ms=duration,sample_rate=info.samplerate,
        channels=info.channels,clips_initialized=True,clips=[Clip(id='clip',source_end_ms=duration)])]
    shutil.copyfile(source,storage.audio_path(project.id,'piano.wav'));storage.save_project(project)
    client=TestClient(app)
    response=client.post(f'/api/projects/{project.id}/ai-studio/jobs',headers={'X-MTA-Request':'1'},json={
        'operation':'audio-to-midi','mode':'accurate','track_ids':['piano'],'end_ms':duration})
    assert response.status_code==200,response.text
    jid=response.json()['job_id'];deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        state=client.get(f'/api/projects/{project.id}/ai-studio/jobs/{jid}').json()
        if state['job']['state'] not in ('queued','running','blocked'):break
        time.sleep(.1)
    assert state['job']['state']=='completed',state
    saved=storage.load_project(project.id)
    assert state['imported'] and len(saved.music_alternatives)>=2
    result=client.get(f'/api/projects/{project.id}/ai-studio/jobs/{jid}/result').json()
    report=json.loads((folder(jid)/'reconciliation-0.json').read_text())
    assert report['comparisons'][0]['matched_events']>=1
    revision=client.get(f'/api/projects/{project.id}/midi/revision').json()['revision']
    for _ in range(2):
        response=client.post(f'/api/projects/{project.id}/midi/alternatives/{saved.music_alternatives[0].id}/import',headers={'X-MTA-Request':'1'},json={'expected_revision':revision})
        assert response.status_code==200,response.text
    assert len(storage.load_project(project.id).tracks)==len(saved.tracks)+1
    if os.getenv('MTA_TEST_ACCURATE_REPORT'):
        Path(os.environ['MTA_TEST_ACCURATE_REPORT']).write_text(json.dumps({'verified':True,
            'source':'Authorized three-note FluidR3 piano fixture, not a mixed-instrument benchmark',
            'actual_models':['YourMT3 noPS 5e66c1ea','Basic Pitch 0.4.0 ONNX CPU'],
            'parts':len(result['parts']),'notes':sum(len(p['notes']) for p in result['parts']),
            'alternatives':len(saved.music_alternatives),'cpu_seconds':state['job']['cpu_seconds'],
            'reconciliation':report,'reopen_verified':True,'alternative_import_idempotent':True,
            'rocm_verified':False,'quality_comparison_claimed':False},indent=2)+'\n')
