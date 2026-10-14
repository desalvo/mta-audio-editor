"""Consistent fail-closed result checks for both remote inference and recovery."""
from unittest.mock import patch
from urllib.error import HTTPError
import io
import pytest
from app.ai_remote_client import infer_audio, recover_audio, RemoteAIError

class Result:
    def __init__(self, body=b'RIFFtest', **headers):
        self.body = io.BytesIO(body)
        self.headers = {'Content-Type': 'audio/wav', 'X-MTA-AI-Job-ID': 'job-123', **headers}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, n): return self.body.read(n)

@pytest.mark.parametrize('response', [
    Result(b''), Result(b'a', **{'Content-Length':'2'}),
    Result(b'a', **{'Content-Length':'-1'}), Result(b'a', **{'Content-Length':'bogus'}),
    Result(b'a', **{'X-MTA-AI-Job-ID':'bad\nvalue'}),
    Result(b'a', **{'X-MTA-AI-Job-ID':'x'*129}),
])
@pytest.mark.parametrize('recover', [False, True])
def test_bad_result_rejected_for_post_and_get(response, recover):
    with patch('app.ai_remote_client.https_urlopen', return_value=response):
        with pytest.raises(RemoteAIError):
            if recover:
                recover_audio('https://example.org', 'token', 'request-key-123456789')
            else:
                infer_audio('https://example.org', 'token', 'whisper', b'RIFF', recover_on_failure=False)

def test_conflicting_request_does_not_trigger_recovery():
    seen=[]
    def conflict(req, **kwargs):
        seen.append(req.get_method())
        raise HTTPError(req.full_url,409,'conflicting request',{},None)
    with patch('app.ai_remote_client.https_urlopen', side_effect=conflict):
        with pytest.raises(RemoteAIError):
            infer_audio('https://example.org','token','whisper',b'RIFF')
    assert seen == ['POST']
