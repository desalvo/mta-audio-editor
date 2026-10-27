"""Actual web fallback and native-only Studio identity boundaries."""
import time
import wave

import pytest

from app import ai_server_execution as server,studio_compute,auth,ai_arranger_runtime as queue
from test_r210_queue_identity_stem_metering import env as env  # noqa: F401


@pytest.mark.parametrize('flag',['1','true','yes','on','false',''])
def test_auth_diagnostics_never_switch_server_to_unowned_local_inference(monkeypatch,flag):
    from app import main
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH',flag)
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    for kind in ['whisper','chords-ml','markers','demucs','singer-separation','backing-vocals','drumsep']:
        assert main._ai_external_engine(kind)
    assert server.enabled(False) and not server.enabled(True)


@pytest.mark.parametrize('uid',[True,False,-1,1.0,'1',None])
@pytest.mark.parametrize('entry',['public','inner'])
def test_invalid_studio_actor_rejected_before_model_or_config(monkeypatch,uid,entry):
    from app import model_license_policy,native_ai_routing,ai_worker_registry
    monkeypatch.setattr(model_license_policy,'evaluate',lambda *a:pytest.fail('invalid actor read model'))
    monkeypatch.setattr(native_ai_routing,'is_remote',lambda *a:pytest.fail('invalid actor read native config'))
    monkeypatch.setattr(ai_worker_registry,'resolve_worker',lambda *a:pytest.fail('invalid actor resolved worker'))
    with pytest.raises(ValueError,match='Invalid Studio execution owner'):
        (studio_compute.compute if entry=='public' else studio_compute._compute)(uid,'vocal-harmony',{})


@pytest.mark.parametrize('entry',['public','inner','remote'])
def test_server_zero_actor_cannot_read_native_token_or_launch(monkeypatch,entry):
    from app import native_ai_routing,ai_worker_registry
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    monkeypatch.setattr(native_ai_routing,'is_remote',lambda *a:pytest.fail('server read native route'))
    monkeypatch.setattr(native_ai_routing,'_read',lambda:pytest.fail('server read native credential'))
    monkeypatch.setattr(ai_worker_registry,'resolve_worker',lambda *a:pytest.fail('server resolved local worker'))
    with pytest.raises(ValueError,match='requires a native application'):
        if entry=='remote':studio_compute.remote_compute('vocal-harmony',{})
        else:(studio_compute.compute if entry=='public' else studio_compute._compute)(0,'vocal-harmony',{})


@pytest.fixture
def web(env,tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main,storage
    from app.models import Track
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects');storage.ROOT.mkdir()
    monkeypatch.setattr(main,'MEDIA_JOBS',{})
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    project=storage.create_project('Executor boundary')
    audio=storage.audio_path(project.id,'source.wav')
    with wave.open(str(audio),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(44100);stream.writeframes(b'\0\0'*4410)
    project.tracks=[Track(id='track',name='Audio',filename='source.wav',duration_ms=100)]
    storage.save_project(project)
    with TestClient(main.app) as client:yield project,client
    deadline=time.monotonic()+5
    while queue._LOCAL and time.monotonic()<deadline:time.sleep(.02)
    assert not queue._LOCAL


def wait(client,job):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        response=client.get('/api/media-jobs/'+job)
        assert response.status_code==200,response.text
        body=response.json()
        if body['status'] not in ('queued','running','blocked'):return body
        time.sleep(.02)
    raise AssertionError('Job did not reach actual terminal state')


def test_actual_diagnostic_web_job_cannot_execute_local_model(web,monkeypatch):
    from app import main,storage
    project,client=web;called=[]
    monkeypatch.setattr(main,'extract_markers',lambda *a,**k:called.append(True) or [])
    response=client.post(f'/api/projects/{project.id}/tracks/track/extract-markers-jobs',headers={'X-MTA-Request':'1'})
    assert response.status_code==200,response.text
    body=wait(client,response.json()['id'])
    assert body['status']=='failed' and not called
    assert storage.load_project(project.id).markers==[]
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]==0


def test_actual_native_local_analysis_still_publishes_without_server_invoice(web,monkeypatch):
    from app import main,native_ai_routing
    project,client=web;called=[]
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',True)
    monkeypatch.setattr(native_ai_routing,'is_remote',lambda _:False)
    monkeypatch.setattr(main,'extract_markers',lambda *a,**k:called.append(True) or [])
    response=client.post(f'/api/projects/{project.id}/tracks/track/extract-markers-jobs',headers={'X-MTA-Request':'1'})
    assert response.status_code==200,response.text
    assert wait(client,response.json()['id'])['status']=='completed' and called==[True]
    with auth.db() as c:assert c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]==0


@pytest.mark.parametrize('actor',['diagnostic','account'])
def test_server_sync_stem_compat_rejects_before_file_or_model_effects(web,monkeypatch,actor):
    from app import main,storage
    from test_r210_legal_documents import cookie
    project,client=web
    if actor=='account':
        monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH')
        monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
        client.cookies.update(cookie(auth.find_user('admin')['id']))
    monkeypatch.setattr(main,'_copy_limited',lambda *a:pytest.fail('rejected server request copied upload'))
    monkeypatch.setattr(main.STEM_SPLITTER,'available',lambda:pytest.fail('rejected server request resolved model'))
    response=client.post('/api/stems/split',params={'project_id':project.id},
        files={'file':('input.mp3',b'fixture','audio/mpeg')},headers={'X-MTA-Request':'1'})
    assert response.status_code==409 and 'asynchronous' in response.text
    assert len(storage.load_project(project.id).tracks)==1
    with auth.db() as c:assert c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]==0


def test_native_compat_license_denial_is_readable_and_has_no_upload_side_effect(web,monkeypatch):
    from app import main,model_license_policy as policy
    project,client=web
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',True)
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    def denied(*args):raise policy.LicenseDenied('Model disabled pending rights review')
    monkeypatch.setattr(policy,'evaluate',denied)
    monkeypatch.setattr(main,'_copy_limited',lambda *a:pytest.fail('denied native request copied upload'))
    response=client.post('/api/stems/split',params={'project_id':project.id},
        files={'file':('input.mp3',b'fixture','audio/mpeg')},headers={'X-MTA-Request':'1'})
    assert response.status_code==409 and 'rights' in response.text
