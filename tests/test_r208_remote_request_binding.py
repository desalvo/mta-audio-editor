"""Remote result must be linked to its original idempotent request."""
import hashlib
import io
from unittest.mock import patch
import pytest
from app.ai_remote_client import infer_audio, recover_audio, RemoteAIError

class Result:
    def __init__(self, request_id):
        self.headers = {'Content-Type': 'audio/wav', 'X-MTA-AI-Job-ID': 'stable-job',
                        'X-MTA-AI-Result-SHA256': hashlib.sha256(b'RIFFvalue').hexdigest()}
        if request_id is not None:
            self.headers['X-MTA-AI-Request-ID'] = request_id
        self.data = io.BytesIO(b'RIFFvalue')
    def read(self, n): return self.data.read(n)
    def __enter__(self): return self
    def __exit__(self, *args): return False

@pytest.mark.parametrize('recover',[True,False])
@pytest.mark.parametrize('returned',[None,'request-123456789','another-request-123456'])
def test_remote_request_binding(recover, returned):
    with patch('app.ai_remote_client.https_urlopen', return_value=Result(returned)):
        call = (lambda: recover_audio('https://server.example', 'token', 'request-123456789')) if recover else (lambda: infer_audio('https://server.example', 'token', 'whisper', b'RIFF', request_id='request-123456789', recover_on_failure=False))
        if returned == 'another-request-123456':
            with pytest.raises(RemoteAIError, match='different request'): call()
        else:
            assert call()[0] == b'RIFFvalue'
