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


def test_debian_245_process_json_and_host_lxc_mapping(monkeypatch, tmp_path):
    class Result:
        stdout = json.dumps([{'gpu': 0, 'process_info': {
            'name': 'llama-server', 'pid': 21729,
            'memory_usage': {'vram_mem': {'value': 23610740736, 'unit': 'B'}},
            'usage': {'gfx': {'value': 0, 'unit': 'ns'}}}}])
    calls = []
    def fake_run(argv, **kwargs):
        calls.append(argv)
        return Result()
    monkeypatch.setattr(agent.subprocess, 'run', fake_run)
    original_read = agent.pathlib.Path.read_text
    def fake_read(path, *args, **kwargs):
        if str(path) == '/proc/21729/cgroup':
            return '0::/lxc/130/ns/system.slice/ollama.service\n'
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(agent.pathlib.Path, 'read_text', fake_read)
    data = agent.read_snapshot()
    assert calls == [['amd-smi', 'process', '--json']]
    assert data['processes'] == [{'host_pid': 21729, 'gpu': 0,
                                  'host_cgroup': '0::/lxc/130/ns/system.slice/ollama.service\n'}]
    assert data['billing_eligible'] is False


def test_idle_amd_smi_2452_process_snapshot(monkeypatch):
    import json
    from scripts import mta_proxmox_gpu_agent as agent
    class Result:
        stdout = json.dumps([{'gpu': 0, 'process_info': 'No running processes detected'}])
    monkeypatch.setattr(agent.subprocess, 'run', lambda *a, **k: Result())
    snapshot = agent.read_snapshot()
    assert snapshot['processes'] == []
    assert snapshot['billing_eligible'] is False
