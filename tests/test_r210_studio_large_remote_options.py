"""Bounded body transport for real Studio settings, with no external requests."""
import json
from contextlib import nullcontext
import pytest
from app.studio_score import Score,pack_request,unpack_request
from app.music_interchange import MusicResult,MusicPart
from app.models import MidiNote


def score():return Score(music=MusicResult(parts=[MusicPart(id='p',name='Singer',notes=[MidiNote(id='n',pitch=60,start_ms=0,duration_ms=500)])])).model_dump_json().encode()


def options():return {'settings':{'backend':'diffsinger','language':'it','pronunciation':'espeak','lyric_text':'la '*1600,
    'expression':{'curves':{'pitch_cents':[{'time_ms':i*50,'value':0} for i in range(1000)]}}}}


def test_large_lyrics_curves_roundtrip_in_body_and_keep_header_small(monkeypatch,tmp_path):
    from app import ai_remote_client as client
    from app import auth
    # This transport fixture produces synthetic bytes and never loads singer or
    # vocoder weights. Give its data-only adapters an explicit isolated policy;
    # production's unreviewed neural checkpoints remain denied by the real gate.
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path)
    monkeypatch.setenv('MTA_NEURAL_SINGER_POLICY_MODEL','mta-analysis')
    monkeypatch.setenv('MTA_DIFFSINGER_VOCODER_POLICY_MODEL','mta-analysis')
    original=score();settings=options();seen=[]
    def transport(request,timeout):
        seen.append(request)
        assert request.get_header('Content-type')=='application/vnd.mta.studio-request+json'
        assert len(request.get_header('X-mta-ai-options'))<100
        decoded,opts=unpack_request(request.data,'vocal-synthesis')
        assert opts==settings and json.loads(decoded)==json.loads(original)
        return nullcontext(object())
    monkeypatch.setattr(client,'https_urlopen',transport)
    monkeypatch.setattr(client,'_read_verified_result',lambda *a,**k:(b'fixture','application/zip','job'))
    result=client.infer_audio('https://mta.test','fixture-token','vocal-synthesis',original,settings,source_format='score')
    assert result[0]==b'fixture' and len(seen)==1


@pytest.mark.parametrize('value',[{'settings':{'command':'bad'}},{'source_score':'/etc/passwd'},
    {'settings':{'expression':{'curves':{'pitch_cents':[{'time_ms':0,'value':float('nan')}]}}}}])
def test_large_transport_keeps_typed_and_path_validation(value):
    with pytest.raises(ValueError):pack_request(score(),'vocal-synthesis',value)


def test_duplicate_keys_wrong_kind_and_oversize_rejected():
    raw=pack_request(score(),'vocal-synthesis',options())
    with pytest.raises(ValueError):unpack_request(raw,'vocal-harmony')
    with pytest.raises(ValueError):unpack_request(b'{"schema":1,"schema":2}','vocal-synthesis')
    with pytest.raises(ValueError):unpack_request(b' '* (8*1024*1024+1),'vocal-synthesis')


def test_authenticated_endpoint_decodes_large_score_body_before_worker(tmp_path,monkeypatch):
    """Real auth/HTTP routing with a fixture worker, not neural inference."""
    import secrets
    from pathlib import Path
    from fastapi.testclient import TestClient
    from app import auth,ai_access,ai_billing_routes,ai_metering_agent,ai_worker_registry
    from app.main import app
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD',secrets.token_urlsafe(32))
    monkeypatch.setattr(auth,'data_root',lambda:tmp_path)
    auth.init_auth_db();uid=auth.find_user('admin')['id'];issued=ai_access.issue(uid,'Studio fixture')
    captured=[]
    def execute(user,kind,plan,**kwargs):
        captured.append((user,kind,plan,kwargs));return b'fixture output',{}
    monkeypatch.setattr(ai_worker_registry,'resolve_worker',lambda *a:Path(__file__))
    monkeypatch.setattr(ai_metering_agent,'execute_registered_worker',execute)
    monkeypatch.setattr(ai_billing_routes,'_verified_worker_response',lambda *a,**k:('fixture-job','application/zip'))
    monkeypatch.setattr(ai_billing_routes,'_remote_metering_headers',lambda *a,**k:{})
    headers={'Authorization':'Bearer '+issued['token'],'Content-Type':'application/vnd.mta.studio-request+json'}
    body=pack_request(score(),'vocal-synthesis',options());client=TestClient(app)
    response=client.post('/api/ai-jobs/execute-audio/vocal-synthesis',headers=headers,content=body)
    assert response.status_code==200,response.text
    assert captured[0][0]==uid and captured[0][2]['settings']==options()['settings']
    assert json.loads(captured[0][3]['source_json'])==json.loads(score())
    response=client.post('/api/ai-jobs/execute-audio/vocal-synthesis',headers={**headers,'X-MTA-AI-Options':'eyJzZXR0aW5ncyI6e319'},content=body)
    assert response.status_code==422 and len(captured)==1
