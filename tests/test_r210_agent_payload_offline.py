"""Protocol validation remains covered when real Unix IPC is unavailable."""
import json
import time
import pytest
from app import ai_proxmox_gpu_agent_client as client


def response(monkeypatch,payload):
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def settimeout(self,value):pass
        def connect(self,path):assert path=='/fixture/agent.sock'
        def sendall(self,data):assert json.loads(data)['token']=='x'*32
        def recv(self,size):return json.dumps(payload).encode()+b'\n'
    monkeypatch.setattr(client.socket,'socket',lambda *args:Connection())


def payload(**changes):
    value={'schema':'mta-gpu-host-agent-v1','timestamp':int(time.time()),
           'source':'host-amd-smi','processes':[{'host_pid':124,'gpu':0,'host_cgroup':'/private'}],
           'billing_eligible':False}
    value.update(changes)
    return value


@pytest.mark.parametrize('changes',[
    {'schema':'wrong'},{'timestamp':0},{'timestamp':'now'},
    {'processes':None},{'processes':[{'host_pid':True,'gpu':0}]},
    {'processes':[{'host_pid':22,'gpu':'0'}]},
    {'processes':[{'host_pid':22,'gpu':0,'host_cgroup':[]}]},
    {'billing_eligible':True},
])
def test_malformed_payload_cannot_authorize_billing(monkeypatch,changes):
    response(monkeypatch,payload(**changes))
    result=client.snapshot(socket_path='/fixture/agent.sock',token='x'*32)
    assert result['available'] is False and result['billing_eligible'] is False


def test_valid_payload_diagnostic_redacts_host_identity(monkeypatch):
    response(monkeypatch,payload())
    result=client.diagnostics(socket_path='/fixture/agent.sock',token='x'*32)
    assert result['authenticated'] is True and result['process_count']==1
    assert result['billing_eligible'] is False and result['billable_gpu_time_verified'] is False
    serialized=json.dumps(result)
    assert '/private' not in serialized and '124' not in serialized and 'x'*32 not in serialized
