"""Real authenticated score worker through the existing remote token protocol."""
import contextvars
import io
import json
import secrets
from email.message import Message
from urllib.error import HTTPError
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from app import auth,ai_access,ai_arranger_runtime as queue
from app.models import MidiNote
from app.music_interchange import MusicResult,MusicPart
from app.studio_score import Score


def test_native_remote_score_token_queue_cpu_and_durable_recovery(tmp_path,monkeypatch):
    from app.main import app
    from app import native_ai_routing,ai_remote_client
    from app.studio_compute import remote_compute
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD',secrets.token_urlsafe(32))
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG',str(tmp_path/'native-workers.json'))
    monkeypatch.setattr(auth,'data_root',lambda:tmp_path/'data')
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT',raising=False)
    auth.init_auth_db();uid=auth.find_user('admin')['id'];issued=ai_access.issue(uid,'Native instance test')
    native_ai_routing.configure('vocal-harmony','remote','https://mta.test',issued['token'])
    client=TestClient(app);requests=[]
    class Response:
        def __init__(self,response):
            self.headers=Message()
            for key,value in response.headers.items():self.headers[key]=value
            self.body=io.BytesIO(response.content)
        def read(self,n):return self.body.read(n)
        def __enter__(self):return self
        def __exit__(self,*args):pass
    def transport(request,timeout):
        requests.append((request.get_method(),urlsplit(request.full_url).path))
        # Separate logical server context: never inherit a native queue job.
        response=contextvars.Context().run(client.request,request.get_method(),urlsplit(request.full_url).path,
            headers=dict(request.header_items()),content=request.data)
        if response.status_code>=400:raise HTTPError(request.full_url,response.status_code,response.text,response.headers,None)
        return Response(response)
    monkeypatch.setattr(ai_remote_client,'https_urlopen',transport)
    score=Score(music=MusicResult(parts=[MusicPart(id='melody',name='Melody',notes=[MidiNote(id='n1',start_ms=0,duration_ms=600,pitch=72)])])).model_dump_json().encode()
    result,meta=remote_compute('vocal-harmony',{'settings':{'voices':4}},score=score)
    assert len(result.parts)==4 and meta['usage']['cpu_seconds']>0 and meta['billable'] is False
    # Simulate a client crash before local publication/acknowledgment.
    repeated,replayed=remote_compute('vocal-harmony',{'settings':{'voices':4}},score=score)
    assert repeated==result and replayed['remote_job_id']==meta['remote_job_id']
    assert sum(method=='POST' and '/execute-audio/' in path for method,path in requests)==1
    with auth.db() as con:
        rows=con.execute('SELECT token_id,status,usage_json FROM ai_compute_jobs').fetchall()
    assert len(rows)==1 and rows[0]['token_id']==issued['id'] and rows[0]['status']=='done'
    assert json.loads(rows[0]['usage_json'])['cpu_seconds']==meta['usage']['cpu_seconds']
    replayed['acknowledge']()
    from app.ai_native_remote_journal import list_pending
    assert list_pending()==[]


def test_score_cannot_be_sent_to_an_audio_model_or_use_untrusted_paths():
    import pytest
    from app.ai_remote_client import infer_audio
    with pytest.raises(ValueError,match='Unsupported remote source'):
        infer_audio('https://mta.test','token','demucs',b'{}',source_format='score')
    from app.ai_remote_transport import validate_audio_options
    with pytest.raises(ValueError,match='forbidden'):
        validate_audio_options({'source_score':'/etc/passwd'})
