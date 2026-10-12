import json
import socket
import threading
import time
from scripts.mta_gpu_agent_ct_diagnostic import probe


def test_missing_mount_is_not_billable(tmp_path):
    result = probe(directory=str(tmp_path))
    assert result['authenticated'] is False
    assert result['billing_eligible'] is False
    assert result['billable_gpu_time_verified'] is False


def test_live_diagnostic_redacts_secrets_and_pid(tmp_path):
    secret = 'a' * 48
    (tmp_path / 'token').write_text(secret)
    target = tmp_path / 'agent.sock'
    ready = threading.Event()
    def serve():
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(str(target))
            listener.listen(1)
            ready.set()
            with listener.accept()[0] as conn:
                request = json.loads(conn.recv(4096))
                assert request['token'] == secret
                payload = {'schema': 'mta-gpu-host-agent-v1', 'source': 'host-amd-smi',
                           'timestamp': int(time.time()), 'billing_eligible': False,
                           'processes': [{'gpu': 0, 'host_pid': 12345, 'host_cgroup': '/sensitive'}]}
                conn.sendall((json.dumps(payload) + '\n').encode())
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(2)
    result = probe(directory=str(tmp_path))
    thread.join(2)
    assert result['authenticated'] is True
    assert result['process_count'] == 1
    assert result['gpu_ids'] == [0]
    assert result['billing_eligible'] is False
    serialized = json.dumps(result)
    assert secret not in serialized and '12345' not in serialized and '/sensitive' not in serialized
