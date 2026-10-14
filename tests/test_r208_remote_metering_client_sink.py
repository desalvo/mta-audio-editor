import hashlib
import io
import json
from types import SimpleNamespace

import pytest
from app.ai_remote_client import _read_verified_result, RemoteAIError
from app.ai_remote_metering_attestation import sign_rotating

KEY = b'A' * 32


def response(envelope=None):
    data = b'{"ok":true}'
    headers = {'Content-Type': 'application/json', 'Content-Length': str(len(data)),
               'X-MTA-AI-Job-ID': 'job1', 'X-MTA-AI-Request-ID': 'req1',
               'X-MTA-AI-Result-SHA256': hashlib.sha256(data).hexdigest()}
    if envelope is not None:
        headers['X-MTA-AI-Metering-V2'] = json.dumps(envelope)
    return SimpleNamespace(headers=headers, read=lambda n: data[:n])


def envelope(**changes):
    item = sign_rotating(KEY, key_id='key1', job_id='job1', request_id='req1',
                         worker_id='worker1', usage={'cpu_seconds': 1.5})
    item.update(changes)
    return item


def read(resp, sink):
    return _read_verified_result(resp, expected_request_id='req1',
                                 metering_sink=sink, metering_keyring={'key1': KEY})


def test_valid_attested_result_passes_measured_evidence():
    calls = []
    assert read(response(envelope()), lambda env, usage: calls.append((env, usage)))[2] == 'job1'
    assert calls[0][1] == {'cpu_seconds': 1.5}


@pytest.mark.parametrize('change', [
    {'signature': '0' * 64}, {'request_id': 'other'}, {'job_id': 'other'},
    {'worker_id': 'different'}, {'key_id': 'revoked'},
    {'usage': {'cpu_seconds': 500}}, {'schema_version': 1},
])
def test_reject_bad_attestation_without_sink(change):
    calls = []
    with pytest.raises(RemoteAIError):
        read(response(envelope(**change)), lambda *args: calls.append(args))
    assert calls == []


def test_requires_attestation_when_sink_enabled():
    with pytest.raises(RemoteAIError):
        read(response(), lambda *args: None)


def test_no_sink_preserves_legacy_response_compatibility():
    assert _read_verified_result(response(), expected_request_id='req1')[2] == 'job1'


def test_sink_not_called_if_result_digest_wrong():
    resp = response(envelope())
    resp.headers['X-MTA-AI-Result-SHA256'] = 'f' * 64
    calls = []
    with pytest.raises(RemoteAIError):
        read(resp, lambda *args: calls.append(args))
    assert not calls
