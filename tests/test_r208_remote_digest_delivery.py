"""Result digest must agree with exactly the downloaded bytes for POST and GET."""
import hashlib
import io
from unittest.mock import patch
import pytest
from app.ai_remote_client import RemoteAIError, infer_audio, recover_audio

class RemoteResult:
    def __init__(self, payload=b'RIFF-real', digest=None):
        self.body = io.BytesIO(payload)
        self.headers = {'Content-Type':'audio/wav','X-MTA-AI-Job-ID':'job-123',
                        'X-MTA-AI-Result-SHA256': digest if digest is not None else hashlib.sha256(payload).hexdigest()}
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n): return self.body.read(n)

@pytest.mark.parametrize('recovery',[False,True])
def test_digest_valid(recovery):
    with patch('app.ai_remote_client.https_urlopen', return_value=RemoteResult()):
        result = recover_audio('https://example.org','token','request-key-123456789') if recovery else infer_audio('https://example.org','token','whisper',b'RIFF',recover_on_failure=False)
    assert result[0] == b'RIFF-real'

@pytest.mark.parametrize('recovery',[False,True])
@pytest.mark.parametrize('digest',['0'*64,'ABC','z'*64,'0'*63])
def test_digest_invalid(recovery,digest):
    with patch('app.ai_remote_client.https_urlopen', return_value=RemoteResult(digest=digest)):
        with pytest.raises(RemoteAIError):
            recover_audio('https://example.org','token','request-key-123456789') if recovery else infer_audio('https://example.org','token','whisper',b'RIFF',recover_on_failure=False)
