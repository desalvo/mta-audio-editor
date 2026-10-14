"""Strict transport contract for sensitive remote AI workflows."""
import hashlib
from unittest.mock import patch
import pytest
from app.ai_remote_client import (RemoteAIError, infer_audio, recover_audio)

KEY = 'request-key-123456789'


class Response:
    def __init__(self, *, digest=True, binding=True, wrong_digest=False):
        self.payload = b'RIFF' + (36).to_bytes(4, 'little') + b'WAVE' + b'fmt ' + (16).to_bytes(4, 'little') + b'\x01\x00\x01\x00' + (8000).to_bytes(4, 'little') + (16000).to_bytes(4, 'little') + b'\x02\x00\x10\x00' + b'data' + (0).to_bytes(4, 'little')
        self.headers = {'Content-Type': 'audio/wav', 'Content-Length': str(len(self.payload)),
                        'X-MTA-AI-Job-ID': 'worker-job-123'}
        if digest:
            self.headers['X-MTA-AI-Result-SHA256'] = ('0' * 64 if wrong_digest else hashlib.sha256(self.payload).hexdigest())
        if binding:
            self.headers['X-MTA-AI-Request-ID'] = KEY
    def read(self, amount):
        return self.payload[:amount]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


@pytest.mark.parametrize('recovery', [False, True])
@pytest.mark.parametrize('digest,binding', [(True, True), (False, True), (True, False), (False, False)])
def test_strict_attestation(recovery, digest, binding):
    response = Response(digest=digest, binding=binding)
    with patch('app.ai_remote_client.https_urlopen', return_value=response):
        call = (lambda: recover_audio('https://example.org', 'token', KEY, require_attestation=True)) if recovery else (
            lambda: infer_audio('https://example.org', 'token', 'whisper', b'RIFF', request_id=KEY,
                                recover_on_failure=False, require_attestation=True))
        if digest and binding:
            assert call()[0] == response.payload
        else:
            with pytest.raises(RemoteAIError):
                call()


@pytest.mark.parametrize('recovery', [False, True])
def test_legacy_still_supported_only_when_not_strict(recovery):
    response = Response(digest=False, binding=False)
    with patch('app.ai_remote_client.https_urlopen', return_value=response):
        if recovery:
            assert recover_audio('https://example.org', 'token', KEY)[0] == response.payload
        else:
            assert infer_audio('https://example.org', 'token', 'whisper', b'RIFF', request_id=KEY,
                               recover_on_failure=False)[0] == response.payload


def test_bad_digest_still_rejected_in_compat_mode():
    with patch('app.ai_remote_client.https_urlopen', return_value=Response(wrong_digest=True)):
        with pytest.raises(RemoteAIError):
            recover_audio('https://example.org', 'token', KEY)
