"""Proxmox GPU host-agent remains optional, non-billable and fail closed."""
import json
import socket
import threading
from app import ai_proxmox_gpu_agent_client as client
from scripts import mta_proxmox_gpu_agent as agent


def test_missing_agent_never_blocks_billing(monkeypatch):
    monkeypatch.delenv('MTA_AI_GPU_HOST_AGENT_SOCKET', raising=False)
    assert client.snapshot()['reason'] == 'not-configured'
    assert not client.snapshot()['billing_eligible']


def test_missing_agent_token_rejected():
    assert client.snapshot(socket_path='/dev/null', token='') == {
        'available': False, 'reason': 'agent-token-not-configured', 'billing_eligible': False,
    }


def test_malformed_agent_reply_fail_closed(tmp_path):
    target = str(tmp_path / 'gpu.sock')
    ready = threading.Event()
    def responder():
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.bind(target)
            sock.listen(1)
            ready.set()
            conn, _ = sock.accept()
            with conn:
                conn.recv(4096)
                conn.sendall(b'{"schema":"wrong"}\n')
    t = threading.Thread(target=responder, daemon=True)
    t.start()
    assert ready.wait(3)
    value = client.snapshot(socket_path=target, token='x'*32)
    t.join(3)
    assert value['available'] is False
    assert value['billing_eligible'] is False


def test_agent_snapshot_uses_host_proc_only(monkeypatch, tmp_path):
    class P:
        stdout = json.dumps([{'gpu': 0, 'process_list': [{'process_info': {'pid': 99999}}]}])
    monkeypatch.setattr(agent.subprocess, 'run', lambda *a, **k: P())
    result = agent.read_snapshot()
    assert result['processes'][0]['host_pid'] == 99999
    assert result['billing_eligible'] is False
    assert result['processes'][0]['host_cgroup'] is None


def test_agent_server_requires_strong_token(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        agent.serve(str(tmp_path/'bad.sock'), 'weak')
