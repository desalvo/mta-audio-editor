"""Host-agent trust-boundary and billing UI usability regressions."""
import json
import socket
import threading
import time
from pathlib import Path

import pytest

from app import ai_proxmox_gpu_agent_client as client
from scripts import mta_proxmox_gpu_agent as agent


def _serve_once(path, payload):
    ready = threading.Event()

    def serve():
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.bind(str(path))
            sock.listen(1)
            ready.set()
            connection, _ = sock.accept()
            with connection:
                connection.recv(4096)
                connection.sendall((json.dumps(payload) + '\n').encode())

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(2)
    return thread


def _payload(**changes):
    value = {'schema': 'mta-gpu-host-agent-v1', 'timestamp': int(time.time()),
             'processes': [{'host_pid': 124, 'gpu': 0, 'host_cgroup': '0::/lxc.scope'}],
             'billing_eligible': False}
    value.update(changes)
    return value


@pytest.mark.parametrize('change', [
    {'timestamp': 0}, {'timestamp': 'now'},
    {'processes': None}, {'processes': [{'host_pid': True, 'gpu': 0}]},
    {'processes': [{'host_pid': 22, 'gpu': '0'}]},
    {'processes': [{'host_pid': 22, 'gpu': 0, 'host_cgroup': []}]},
    {'billing_eligible': True},
])
def test_agent_rejects_untrusted_snapshot(tmp_path, change, unix_socket_capability):
    path = tmp_path / 'agent.sock'
    thread = _serve_once(path, _payload(**change))
    result = client.snapshot(socket_path=str(path), token='x' * 32)
    thread.join(2)
    assert result['available'] is False
    assert result['billing_eligible'] is False


def test_valid_agent_snapshot_is_diagnostic_only(tmp_path, unix_socket_capability):
    path = tmp_path / 'agent.sock'
    thread = _serve_once(path, _payload())
    result = client.snapshot(socket_path=str(path), token='x' * 32)
    thread.join(2)
    assert result['available'] is True
    assert result['billing_eligible'] is False


def test_billing_dashboard_sends_valid_gpu_preview_window():
    html = Path(__file__).resolve().parents[1] / 'app' / 'templates' / 'ai_billing.html'
    source = html.read_text(encoding='utf-8')
    assert 'start_ms:String(start),end_ms:String(end)' in source
    assert 'Costo a tariffe configurate' in source
    assert 'Non vengono applicati automaticamente ai job' in source


def test_agent_rejects_bad_device_ids(monkeypatch):
    class P:
        stdout = json.dumps([{'gpu': 'zero', 'process_list': []}])
    monkeypatch.setattr(agent.subprocess, 'run', lambda *args, **kwargs: P())
    with pytest.raises(ValueError, match='GPU ID'):
        agent.read_snapshot()
