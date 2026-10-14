from unittest.mock import patch
import pytest
from app import ai_metering_bridge as bridge, ai_remote_metering_attestation as attest

K = b'z'*32

@pytest.mark.parametrize('usage', [
    {'cpu_seconds': 0}, {'cpu_seconds': .1}, {'cpu_seconds': 3},
    {'cpu_seconds': 10000}, {'cpu_seconds': 1, 'read_bytes': 0},
    {'cpu_seconds': 1, 'read_bytes': 1024},
    {'cpu_seconds': 1, 'write_bytes': 0},
    {'cpu_seconds': 1, 'write_bytes': 4096},
    {'cpu_seconds': 1, 'read_bytes': 13, 'write_bytes': 42},
])
def test_verified_cpu_evidence_handoff(usage):
    envelope = attest.sign(K,job_id='job_123',request_id='req_123',worker_id='worker_1',usage=usage)
    with patch.object(bridge, '_identity', return_value=(5,'arranger')) as ident, \
         patch.object(bridge,'capture',return_value=True) as capture:
        assert bridge.capture_authenticated_remote('job_123', envelope,request_id='req_123',worker_id='worker_1',worker_key=K)
        ident.assert_called_once_with('job_123')
        capture.assert_called_once_with('job_123', usage, 'remote-worker')

@pytest.mark.parametrize('mismatch', ['job','request','worker','key','usage'])
def test_invalid_evidence_never_reaches_storage(mismatch):
    envelope = attest.sign(K,job_id='job_123',request_id='req_123',worker_id='worker_1',usage={'cpu_seconds':2})
    args = {'request_id':'req_123','worker_id':'worker_1','worker_key':K}
    if mismatch == 'job': envelope['job_id'] = 'job_fake'
    if mismatch == 'request': args['request_id'] = 'req_other'
    if mismatch == 'worker': args['worker_id'] = 'other_worker'
    if mismatch == 'key': args['worker_key'] = b'q'*32
    if mismatch == 'usage': envelope['usage']['cpu_seconds'] = 500
    with patch.object(bridge,'_identity',return_value=(5,'arranger')), \
         patch.object(bridge,'capture') as capture:
        with pytest.raises(ValueError):
            bridge.capture_authenticated_remote('job_123',envelope,**args)
        capture.assert_not_called()
