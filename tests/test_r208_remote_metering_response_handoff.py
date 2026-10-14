import json
import pytest
from app import ai_billing_routes as routes
from app.ai_remote_metering_attestation import verify_rotating

KEY = bytes.fromhex('ab'*32)


def test_no_operator_key_yields_legacy_response(monkeypatch):
    monkeypatch.delenv('MTA_AI_REMOTE_METERING_SIGNING_KEY_ID', raising=False)
    assert routes._remote_metering_headers({'job_id':'j','process_tree_metered':True,'usage':{'cpu_seconds':2}}, 'req') == {}


def test_signs_isolated_cpu_for_original_request(monkeypatch):
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_SIGNING_KEY_ID','key1')
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_WORKER_ID','worker1')
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON',json.dumps({'key1':KEY.hex()}))
    meta={'job_id':'job1','process_tree_metered':True,'usage':{'cpu_seconds':1.5, 'gpu_seconds':12}}
    header=routes._remote_metering_headers(meta,'request1')
    evidence=json.loads(header['X-MTA-AI-Metering-V2'])
    assert verify_rotating({'key1':KEY}, evidence,job_id='job1',request_id='request1',worker_id='worker1') == {'cpu_seconds':1.5}
    with pytest.raises(ValueError,match='mismatch'):
        verify_rotating({'key1':KEY},evidence,job_id='job1',request_id='other',worker_id='worker1')

@pytest.mark.parametrize('meta,key',[
    ({'job_id':'job1','process_tree_metered':False,'usage':{'cpu_seconds':2}},'r'),
    ({'job_id':'job1','process_tree_metered':True,'usage':{}},'r'),
    ({'job_id':'job1','process_tree_metered':True,'usage':{'cpu_seconds':2}},''),
])
def test_does_not_sign_unverified_metering(monkeypatch,meta,key):
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_SIGNING_KEY_ID','key1')
    assert routes._remote_metering_headers(meta,key) == {}


def test_revoked_key_fails_closed(monkeypatch):
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_SIGNING_KEY_ID','revoked')
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_WORKER_ID','worker1')
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON',json.dumps({'other':KEY.hex()}))
    with pytest.raises(ValueError, match='revoked'):
        routes._remote_metering_headers({'job_id':'job1','process_tree_metered':True,'usage':{'cpu_seconds':3}},'r')
