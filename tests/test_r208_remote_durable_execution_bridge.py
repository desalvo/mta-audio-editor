"""Regression checks for durable metered remote invocation."""
import hashlib
import pytest
from app import ai_metering_bridge as bridge


def test_remote_inference_binds_every_receipt(monkeypatch):
    seen = []
    monkeypatch.setattr(bridge, '_identity', lambda job: (7, 'arranger'))
    monkeypatch.setattr('app.ai_remote_keyring.active_keyring', lambda: {'primary': b'x' * 32})
    monkeypatch.setattr(bridge, 'durable_remote_sink', lambda job, **kw: seen.append(('sink', job, kw)) or (lambda e, u: None))
    monkeypatch.setattr('app.ai_remote_client.infer_audio', lambda *args, **kwargs: seen.append(('remote', args, kwargs)) or (b'audio', 'audio/wav', 'remote123'))
    result = bridge.infer_durable_remote('local-123', base_url='https://example.org', token='s', wav=b'fake', worker_id='node_2')
    assert result[2] == 'remote123'
    assert seen[0][2]['request_id'] == hashlib.sha256(b'mta-remote-v1:local-123').hexdigest()
    assert seen[1][2]['request_id'] == seen[0][2]['request_id']
    assert seen[1][2]['metering_sink'] is not None
    assert seen[1][2]['metering_keyring'] == {'primary': b'x' * 32}
    assert seen[1][2]['require_attestation'] is True
    assert seen[1][1][2] == 'arranger'


@pytest.mark.parametrize('worker_id', ['', 'x y', 'a'*129, 4, '../etc', 'é'])
def test_remote_bad_worker_rejected_before_network(monkeypatch, worker_id):
    monkeypatch.setattr(bridge, '_identity', lambda job: (7, 'remix'))
    with pytest.raises(ValueError):
        bridge.infer_durable_remote('local-123', base_url='https://example.org', token='s', wav=b'a', worker_id=worker_id)


def test_remote_requires_operator_keys(monkeypatch):
    monkeypatch.setattr(bridge, '_identity', lambda job: (7, 'remix'))
    monkeypatch.setattr('app.ai_remote_keyring.active_keyring', lambda: {})
    with pytest.raises(ValueError, match='trusted'):
        bridge.infer_durable_remote('local-123', base_url='https://example.org', token='s', wav=b'a', worker_id='node')
