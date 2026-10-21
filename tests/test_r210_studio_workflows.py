"""Real harmony worker, queue publication, permissions and cancellation gates."""
import time

import pytest
from fastapi.testclient import TestClient
from app import storage,auth,ai_arranger_runtime as queue
from app.models import Track,Clip,MidiNote
from app.main import app


@pytest.fixture
def studio(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true')
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path/'worker-data'))
    monkeypatch.setattr(auth,'data_root',lambda:tmp_path/'account')
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects');storage.ROOT.mkdir()
    project=storage.create_project('Harmony',target='DAW_MIDI')
    project.tracks=[Track(id='melody',name='Melody',filename='anchor.wav',kind='midi',duration_ms=3000,
        clips_initialized=True,clips=[Clip(id='clip',source_end_ms=3000)],
        midi_notes=[MidiNote(id=f'n{i}',pitch=n,start_ms=i*500,duration_ms=400) for i,n in enumerate([72,74,76,77])])]
    # Media anchor required by the editor, not used for synthesis.
    import wave
    with wave.open(str(storage.audio_path(project.id,'anchor.wav')),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b'\0\0'*64)
    storage.save_project(project)
    return project,TestClient(app)


def start(studio,**kwargs):
    project,client=studio
    body={'operation':'vocal-harmony','track_ids':['melody'],'start_ms':0,'end_ms':3000,
          'settings':{'voices':4,'key':'C'},**kwargs}
    response=client.post(f'/api/projects/{project.id}/ai-studio/jobs',headers={'X-MTA-Request':'1'},json=body)
    assert response.status_code==200,response.text
    return response.json()['job_id']


def wait(studio,job_id):
    p,c=studio;deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        data=c.get(f'/api/projects/{p.id}/ai-studio/jobs/{job_id}').json()
        if data['job']['state'] not in ('running','queued','blocked'):return data
        time.sleep(.05)
    raise AssertionError('Real harmony job did not finish')


def test_real_harmony_queue_auto_publication_and_reopen(studio):
    job_id=start(studio);data=wait(studio,job_id)
    assert data['job']['state']=='completed',data['job']['message']
    assert data['imported']
    project=storage.load_project(studio[0].id)
    assert len(project.tracks)==5
    assert len(project.music_imports)==1
    assert all(len(t.midi_notes)==4 for t in project.tracks[1:])
    assert all(t.music_result_id==job_id for t in project.tracks[1:])
    assert data['job']['cpu_seconds']>0
    assert data['job']['gpu_seconds'] is None
    assert all(storage.audio_path(project.id,t.filename).is_file() for t in project.tracks)


def test_results_can_be_reviewed_and_imported_idempotently(studio):
    job_id=start(studio,auto_import=False);data=wait(studio,job_id)
    assert data['job']['state']=='completed' and not data['imported'],data['job']['message']
    p,c=studio
    assert len(storage.load_project(p.id).tracks)==1
    result=c.get(f'/api/projects/{p.id}/ai-studio/jobs/{job_id}/result').json()
    assert len(result['parts'])==4
    rev=c.get(f'/api/projects/{p.id}/midi/revision').json()['revision']
    for _ in range(2):
        response=c.post(f'/api/projects/{p.id}/ai-studio/jobs/{job_id}/import',json={'expected_revision':rev},headers={'X-MTA-Request':'1'})
        assert response.status_code==200,response.text
    assert len(storage.load_project(p.id).tracks)==5


def test_studio_validates_source_range_and_harmony_settings(studio):
    p,c=studio
    for values in ({'end_ms':0},{'settings':{'voices':9}},{'track_ids':['missing']},{'track_ids':['melody','melody']}):
        body={'operation':'vocal-harmony','track_ids':['melody'],'end_ms':3000,**values}
        assert c.post(f'/api/projects/{p.id}/ai-studio/jobs',json=body,headers={'X-MTA-Request':'1'}).status_code==422


def test_score_transport_denies_client_paths_before_running(studio):
    from app.ai_metering_agent import _execute_registered_worker
    with pytest.raises(ValueError,match='Score path'):
        _execute_registered_worker(1,'vocal-harmony',{'source_score':'/etc/passwd'})


def test_commit_gate_rejects_ambiguous_late_cancellation(studio):
    jid='a'*32
    queue.start(studio[0].id,'worker:studio-music',lambda p:None,job_id=jid,defer_spawn=True)
    with queue._db() as con:con.execute("UPDATE jobs SET state='running',phase='studio-committing' WHERE job_id=?",(jid,))
    with pytest.raises(ValueError,match='publication'):queue.cancel(jid)
    assert not queue.get(jid)['cancel_requested']


def test_manual_import_updates_publication_receipt(studio):
    jid=start(studio,auto_import=False);wait(studio,jid)
    p,c=studio
    rev=c.get(f'/api/projects/{p.id}/midi/revision').json()['revision']
    response=c.post(f'/api/projects/{p.id}/ai-studio/jobs/{jid}/import',json={'expected_revision':rev},headers={'X-MTA-Request':'1'})
    assert response.status_code==200,response.text
    assert c.get(f'/api/projects/{p.id}/ai-studio/jobs/{jid}').json()['imported']


def test_zero_credit_admission_is_actionable(studio,monkeypatch):
    from app.resource_access import CreditAdmissionError
    from app import resource_access
    def reject(_owner):raise CreditAdmissionError('CREDITS_EXHAUSTED: No remaining credits')
    monkeypatch.setattr(resource_access,'preflight',reject)
    p,c=studio
    response=c.post(f'/api/projects/{p.id}/ai-studio/jobs',json={'operation':'vocal-harmony','track_ids':['melody'],'end_ms':3000},headers={'X-MTA-Request':'1'})
    assert response.status_code==402,response.text
    assert response.json()['code']=='credits_exhausted'
    assert 'administrator' in response.json()['action']
    with queue._db() as con:assert con.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==0


def test_retention_only_removes_terminal_private_results(studio):
    from app.studio_jobs import folder,cleanup_expired
    jid=start(studio);wait(studio,jid)
    queue.start(studio[0].id,'worker:studio-music',lambda p:None,job_id='b'*32,defer_spawn=True)
    folder('b'*32).mkdir()
    old=time.time()-8*86400
    with queue._db() as con:con.execute('UPDATE jobs SET completed_at=? WHERE job_id=?',(old,jid))
    assert cleanup_expired()==1
    assert not folder(jid).exists()
    assert folder('b'*32).exists()
    assert len(storage.load_project(studio[0].id).tracks)==5


def test_source_region_uses_clip_offset_delay_and_gain(tmp_path):
    import numpy as np
    import soundfile as sf
    from app.studio_audio import prepare
    source=tmp_path/'source.wav';output=tmp_path/'region.wav';rate=44100
    sf.write(source,np.ones(rate*2)*.2,rate,subtype='FLOAT')
    track=Track(id='audio',name='Audio',filename='source.wav',duration_ms=2000,delay_ms=250,gain_db=-6,
        clips_initialized=True,clips=[Clip(id='clip',source_start_ms=500,source_end_ms=1000,timeline_start_ms=1000)])
    assert prepare(track,source,1000,2000,output,lambda:False)
    data,sr=sf.read(output)
    assert sr==rate and len(data)==rate
    assert abs(data[:int(.24*rate)]).max()<.001
    # FFmpeg's mono-to-stereo remix uses -3 dB per output channel.
    assert .06<float(np.mean(data[int(.3*rate):int(.7*rate)]))<.08
    assert abs(data[int(.8*rate):]).max()<.001


def test_harmony_structured_score_real_server_ledger(tmp_path,monkeypatch):
    import json,secrets
    from app import ai_metering_agent
    from app.studio_score import Score
    from app.music_interchange import MusicPart,MusicResult
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setattr(auth,'data_root',lambda:tmp_path/'data')
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'jobs')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD',secrets.token_urlsafe(32))
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT',raising=False)
    auth.init_auth_db();uid=auth.find_user('admin')['id']
    notes=[MidiNote(id=f'n{i}',start_ms=i*500,duration_ms=400,pitch=72+i%5) for i in range(1800)]
    score=Score(music=MusicResult(parts=[MusicPart(id='source',name='Long melody',notes=notes)]))
    raw=score.model_dump_json().encode();assert len(raw)>256*1024
    payload,meta=ai_metering_agent.execute_registered_worker(uid,'vocal-harmony',{'settings':{'voices':4}},source_json=raw,timeout_seconds=60)
    assert payload and meta['usage']['cpu_seconds']>0
    with auth.db() as con:
        row=con.execute('SELECT kind,status,usage_json FROM ai_compute_jobs WHERE id=?',(meta['job_id'],)).fetchone()
    assert row['kind']=='vocal-harmony' and row['status']=='done'
    assert json.loads(row['usage_json'])['cpu_seconds']==meta['usage']['cpu_seconds']


def test_project_changed_during_worker_keeps_reviewable_result(studio,monkeypatch):
    from app import studio_compute
    original=studio_compute.compute
    def compute(*args,**kwargs):
        result=original(*args,**kwargs)
        project=storage.load_project(studio[0].id);project.title='Edited during inference';storage.save_project(project)
        return result
    monkeypatch.setattr(studio_compute,'compute',compute)
    jid=start(studio);data=wait(studio,jid)
    assert data['job']['state']=='completed' and data['result_available'] and not data['imported']
    assert len(storage.load_project(studio[0].id).tracks)==1
    assert 'changed' in data['reason']


def test_private_diagnostics_zip_and_missing_jobs(studio):
    import io,zipfile,json
    p,c=studio;jid=start(studio);wait(studio,jid)
    response=c.get(f'/api/projects/{p.id}/ai-studio/jobs/{jid}/diagnostics.zip')
    assert response.status_code==200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist())=={'job.json','README.txt','publication.json'}
        assert json.loads(archive.read('job.json'))['state']=='completed'
    assert c.get(f'/api/projects/{p.id}/ai-studio/jobs/invalid').status_code==404


def test_admin_policy_is_validated_and_uninstall_protects_active_jobs(studio):
    p,c=studio
    from app.main import NATIVE_SINGLE_USER
    prefix='/api/native/ai/studio' if NATIVE_SINGLE_USER else '/api/admin/ai/studio'
    headers={'X-MTA-Request':'1'}
    for value in ({'timeout_seconds':0,'retention_days':7},{'timeout_seconds':3600,'retention_days':0},{'timeout_seconds':True,'retention_days':7}):
        assert c.put(prefix+'/policy',json=value,headers=headers).status_code==422
    assert c.put(prefix+'/policy',json={'timeout_seconds':1200,'retention_days':2},headers=headers).status_code==200
    assert c.get(prefix+'/models').json()['policy']['retention_days']==2
    queue.start(p.id,'worker:studio-music',lambda progress:None,job_id='c'*32,defer_spawn=True)
    assert c.delete(prefix+'/models/basic-pitch',headers=headers).status_code==409
