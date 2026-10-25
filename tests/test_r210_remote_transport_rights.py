"""No inference transport bypass; retrieval/control remains available."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import ai_remote_client as remote, ai_gateway as gateway, ace_step_http_worker as ace
from app import model_license_policy as rights, service_regime


@pytest.fixture
def commercial(monkeypatch,tmp_path):
    from app import auth,studio_catalog
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path)
    monkeypatch.setattr(studio_catalog,'root',lambda:tmp_path/'models')
    monkeypatch.setattr(service_regime,'current_regime',lambda:service_regime.Regime.COMMERCIAL)
    monkeypatch.setattr(rights,'overrides',lambda:{})
    monkeypatch.setattr(rights,'commercial_service_enabled',lambda:True)


@pytest.mark.parametrize('kind',['whisper','demucs','audio-to-midi-basic-pitch','audio-to-midi-yourmt3','vocal-harmony','arranger','remix'])
def test_raw_client_commercial_denies_before_source_validation_or_network(commercial,monkeypatch,kind):
    network=Mock(side_effect=AssertionError('No network permitted'))
    monkeypatch.setattr(remote,'https_urlopen',network)
    with rights.admission(rights.Decision('whisper','cost_recovery','https://example.test','old-review')):
        with pytest.raises(rights.LicenseDenied,match='attestation'):
            remote.infer_audio('https://example.test','private-token',kind,b'')
    network.assert_not_called()


@pytest.mark.parametrize('entry',['client','gateway','ace-request','ace-run'])
def test_disabled_nc_policy_cannot_use_direct_transport(monkeypatch,tmp_path,entry):
    monkeypatch.setattr(service_regime,'current_regime',lambda:service_regime.Regime.NON_COMMERCIAL)
    monkeypatch.setattr(rights,'overrides',lambda:{'ace-step':{'mode':'disabled'}})
    monkeypatch.setattr(rights,'commercial_service_enabled',lambda:True)
    monkeypatch.setenv('MTA_ACE_STEP_URL','https://worker.example.test:443')
    monkeypatch.setenv('MTA_ACE_STEP_TRUSTED_HOST','worker.example.test')
    monkeypatch.setenv('MTA_ACE_STEP_TOKEN','private-internal-key')
    network=Mock(side_effect=AssertionError('No network permitted'))
    monkeypatch.setattr(remote,'https_urlopen',network);monkeypatch.setattr(ace,'build_opener',network)
    if entry=='client':
        with pytest.raises(rights.LicenseDenied):remote.infer_audio('https://mta.example.test','test','ace-step',b'audio')
    elif entry=='gateway':
        client,_=gateway_client(monkeypatch)
        response=client.post('/api/ai-gateway/release_task',headers={'authorization':'Bearer valid'},content=b'{}')
        assert response.status_code==403
    elif entry=='ace-request':
        with pytest.raises(rights.LicenseDenied):ace._request('https://worker.example.test:443/release_task',b'{}')
    else:
        plan=tmp_path/'plan.json';plan.write_text(json.dumps({'model_id':'ace-step-1.5'}))
        with pytest.raises(rights.LicenseDenied):ace._run(plan,tmp_path/'missing.wav')
    network.assert_not_called()


def gateway_client(monkeypatch,*,native=False):
    app=FastAPI();app.include_router(gateway.router);sent=[]
    monkeypatch.setattr(gateway.ai_access,'authenticate',lambda _: {'id':1,'user_id':2,**({'client_id':'native'} if native else {})})
    monkeypatch.setattr(gateway.ai_access,'usage',lambda *args:None)
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def request(self,method,url,**kwargs):
            sent.append((method,url,kwargs));return httpx.Response(200,json={'status':'ok'})
    monkeypatch.setattr(httpx,'AsyncClient',Client)
    monkeypatch.setenv('MTA_ACE_STEP_URL','https://private.example.test')
    return TestClient(app),sent


@pytest.mark.parametrize('path',['release_task','v1/init','v1/generate','v1/audio','v1/models'])
def test_gateway_mutations_cannot_forward_commercial_work(commercial,monkeypatch,path):
    client,sent=gateway_client(monkeypatch)
    result=client.post('/api/ai-gateway/'+path,headers={'authorization':'Bearer valid'},content=b'{}')
    assert result.status_code==403 and sent==[] and 'private' not in result.text


@pytest.mark.parametrize('method,path',[('GET','health'),('GET','v1/models'),('GET','v1/audio'),('POST','query_result')])
def test_commercial_metadata_and_existing_task_polling_are_not_new_inference(commercial,monkeypatch,method,path):
    client,sent=gateway_client(monkeypatch)
    result=client.request(method,'/api/ai-gateway/'+path,headers={'authorization':'Bearer valid'},content=b'{}')
    assert result.status_code==200 and len(sent)==1


def test_native_gateway_token_still_cannot_skip_accounted_endpoint(commercial,monkeypatch):
    client,sent=gateway_client(monkeypatch,native=True)
    assert client.post('/api/ai-gateway/query_result',headers={'authorization':'Bearer valid'},content=b'{}').status_code==403
    assert not sent


def test_standalone_remote_worker_denies_before_missing_audio_or_dns(tmp_path,monkeypatch):
    data=tmp_path/'data';data.mkdir();(data/'service-regime.json').write_text('{"regime":"COMMERCIAL","revision":0}')
    from app import auth
    from app.regime_operation_fence import initialize
    monkeypatch.setattr(auth,'DATA_ROOT',data);monkeypatch.setenv('MTA_DATA_DIR',str(data))
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','test-only-strong-password')
    auth.init_auth_db()
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');initialize(c,initial_regime='COMMERCIAL')
    plan=tmp_path/'request.json';plan.write_text('{"model_id":"ace-step-1.5"}')
    result=subprocess.run([sys.executable,str(Path(ace.__file__).resolve()),'--request',str(plan),'--output',str(tmp_path/'output.wav')],
        cwd=tmp_path,env={**os.environ,'MTA_DATA_DIR':str(data),'PYTHONPATH':'','MTA_ACE_STEP_URL':'https://worker.example.test:443',
        'MTA_ACE_STEP_TRUSTED_HOST':'worker.example.test','MTA_ACE_STEP_TOKEN':'private-test-key'},capture_output=True,text=True,timeout=15,check=False)
    assert result.returncode!=0 and 'attestation' in result.stderr
    assert not (tmp_path/'output.wav').exists() and 'private-test-key' not in result.stderr


@pytest.mark.parametrize('path,data',[('/health',None),('/query_result',b'{}'),('/mta/tasks/existing/control',b'{}')])
def test_remote_ace_read_and_cancel_skip_inference_gate(commercial,monkeypatch,path,data):
    monkeypatch.setenv('MTA_ACE_STEP_URL','https://worker.example.test:443')
    monkeypatch.setenv('MTA_ACE_STEP_TRUSTED_HOST','worker.example.test')
    monkeypatch.setenv('MTA_ACE_STEP_TOKEN','private-key')
    gate=Mock(side_effect=AssertionError('Not inference'));monkeypatch.setattr(rights,'authorize_remote_execution',gate)
    class Response:
        headers={}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def geturl(self):return 'https://worker.example.test:443'+path
        def read(self,*args):return b'{}'
    opener=Mock();opener.open.return_value=Response();monkeypatch.setattr(ace,'build_opener',lambda *args:opener)
    assert ace._request('https://worker.example.test:443'+path,data)==b'{}';gate.assert_not_called()


@pytest.mark.parametrize('operation',['status','recover','cancel','list','resources','capabilities'])
def test_client_historical_operations_stay_available_under_commercial_denial(commercial,monkeypatch,operation):
    from urllib.error import URLError
    gate=Mock(side_effect=AssertionError('Historical read/control is not inference'))
    monkeypatch.setattr(rights,'authorize_remote_execution',gate)
    network=Mock(side_effect=URLError('isolated unavailable server'));monkeypatch.setattr(remote,'https_urlopen',network)
    base='https://example.test';token='private-test-token';identifier='a'*32
    invoke={'status':lambda:remote.remote_request_status(base,token,identifier),
            'recover':lambda:remote.recover_audio(base,token,identifier),
            'cancel':lambda:remote.cancel_remote_request(base,token,identifier),
            'list':lambda:remote.list_remote_requests(base,token),
            'resources':lambda:remote.remote_resources(base,token,identifier),
            'capabilities':lambda:remote.studio_capabilities(base,token)}[operation]
    with pytest.raises((remote.RemoteAIError,URLError)):invoke()
    gate.assert_not_called();assert network.call_count==1
    request=network.call_args.args[0];assert '/execute-audio/' not in request.full_url


@pytest.mark.parametrize('url',['http://127.0.0.1:8001','http://localhost:8001','http://[::1]:8001'])
def test_loopback_or_tunnel_does_not_exempt_commercial_inference(commercial,monkeypatch,url):
    monkeypatch.setenv('MTA_ACE_STEP_URL',url)
    opener=Mock(side_effect=AssertionError('No network permitted'));monkeypatch.setattr(ace,'build_opener',opener)
    with pytest.raises(rights.LicenseDenied,match='attestation'):ace._request(url+'/release_task',b'{}')
    opener.assert_not_called()


@pytest.mark.parametrize('path',['/api/ai-gatewayevil/query_result','/xxxxxxxxxxxxxx/query_result','/other/query_result','/release_task'])
def test_gateway_prefix_cannot_be_forged_as_polling_exemption(commercial,monkeypatch,path):
    monkeypatch.setenv('MTA_ACE_STEP_URL','https://worker.example.test:443/api/ai-gateway')
    monkeypatch.setenv('MTA_ACE_STEP_TRUSTED_HOST','worker.example.test')
    monkeypatch.setenv('MTA_ACE_STEP_TOKEN','private-token')
    opener=Mock(side_effect=AssertionError('No network permitted'));monkeypatch.setattr(ace,'build_opener',opener)
    with pytest.raises(ValueError,match='outside.*endpoint'):ace._request('https://worker.example.test:443'+path,b'{}')
    opener.assert_not_called()


def test_configured_gateway_polling_still_works_without_new_inference(commercial,monkeypatch):
    base='https://worker.example.test:443/api/ai-gateway';url=base+'/query_result'
    monkeypatch.setenv('MTA_ACE_STEP_URL',base);monkeypatch.setenv('MTA_ACE_STEP_TRUSTED_HOST','worker.example.test')
    monkeypatch.setenv('MTA_ACE_STEP_TOKEN','private-token')
    gate=Mock(side_effect=AssertionError('Polling is not inference'));monkeypatch.setattr(rights,'authorize_remote_execution',gate)
    class Response:
        headers={}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def geturl(self):return url
        def read(self,*args):return b'{}'
    opener=Mock();opener.open.return_value=Response();monkeypatch.setattr(ace,'build_opener',lambda *args:opener)
    assert ace._request(url,b'{"task_id_list":["existing"]}')==b'{}'
    assert opener.open.call_count==1;gate.assert_not_called()


@pytest.mark.parametrize('kind,options',[(None,{}),(123,{}),([],{}),('whisper',[]),('vocal-synthesis',[]),
    ('whisper','invalid'),('vocal-synthesis',{'settings':[]}),('audio-to-midi-transkun',{'options':[]})])
def test_malformed_model_selection_is_value_error_without_transport(monkeypatch,kind,options):
    monkeypatch.setattr(service_regime,'current_regime',lambda:service_regime.Regime.NON_COMMERCIAL)
    network=Mock(side_effect=AssertionError('No network permitted'));monkeypatch.setattr(remote,'https_urlopen',network)
    with pytest.raises(ValueError):remote.infer_audio('https://example.test','test-token',kind,b'audio',options)
    network.assert_not_called()
