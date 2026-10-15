"""Negative contract matrix for remote AI calls; each case must fail before network I/O."""
import base64

from unittest.mock import patch
import pytest
from app.ai_remote_client import infer_audio, recover_audio, _read_verified_result, RemoteAIError
from app.ai_remote_transport import decode_audio_options

KEY = 'request-key-123456789'

@pytest.mark.parametrize('url', [
 'http://example.org', 'https://user@example.org', 'https://example.org?token=1',
 'https://example.org/#x', 'https://example.org:bogus', 'https://example.org:0',
 'https://example.org/%61pi/ai-jobs', 'https://example.org\\evil',
 'https://example.org:443:', 'https://example.org/api/other',
])
def test_bad_urls_rejected_before_network(url):
    with patch('app.ai_remote_client.https_urlopen') as call:
        with pytest.raises(ValueError):
            infer_audio(url, 'token', 'whisper', b'RIFF', recover_on_failure=False)
        call.assert_not_called()

@pytest.mark.parametrize('token', [None, 1, '', 'two words', 'x\nZ', 'x\rY', 'x\tY', 'é', 'x'*4097])
def test_invalid_tokens_preflight(token):
    with patch('app.ai_remote_client.https_urlopen') as call:
        with pytest.raises(ValueError):
            infer_audio('https://example.org', token, 'whisper', b'RIFF')
        call.assert_not_called()

@pytest.mark.parametrize('timeout', [None, False, 0, -1, float('nan'), float('inf'), '30'])
@pytest.mark.parametrize('recover', [False, True])
def test_invalid_timeouts_preflight(timeout, recover):
    with patch('app.ai_remote_client.https_urlopen') as call:
        with pytest.raises(ValueError):
            if recover:
                recover_audio('https://example.org', 'token', KEY, timeout_seconds=timeout)
            else:
                infer_audio('https://example.org', 'token', 'whisper', b'RIFF', timeout_seconds=timeout)
        call.assert_not_called()

@pytest.mark.parametrize('options', [[], 'abc', 1, float('nan'), {'level': float('inf')}, {'level': object()}, {'': 2}, {'x\\y': 2}])
def test_invalid_options_preflight(options):
    with patch('app.ai_remote_client.https_urlopen') as call:
        with pytest.raises(ValueError):
            infer_audio('https://example.org', 'token', 'whisper', b'RIFF', options=options)
        call.assert_not_called()

@pytest.mark.parametrize('key', [False, 3, [], '', 'short', 'x\n'*16])
def test_invalid_request_id_preflight(key):
    with patch('app.ai_remote_client.https_urlopen') as call:
        with pytest.raises(ValueError):
            infer_audio('https://example.org', 'token', 'whisper', b'RIFF', request_id=key)
        call.assert_not_called()

@pytest.mark.parametrize('raw', [b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}', b'{"":1}', b'{"foo\\\\bar":1}'])
def test_decoder_rejects_invalid_json_values(raw):
    encoded = base64.urlsafe_b64encode(raw).decode().rstrip('=')
    with pytest.raises(ValueError):
        decode_audio_options(encoded)

class FakeResponse:
    def __init__(self, headers):
        self.headers = headers
    def read(self, n): return b'data'

@pytest.mark.parametrize('extra', [
 {'Content-Length':'1'*1000}, {'Content-Length':'-4'},
 {'X-MTA-AI-Request-ID':'x'*300}, {'X-MTA-AI-Result-SHA256':'x'*64},
 {'X-MTA-AI-Job-ID':'x'*129}, {'Content-Type':'text/plain'},
])
def test_invalid_result_headers(extra):
    headers = {'Content-Type':'audio/wav', 'X-MTA-AI-Job-ID':'job123', **extra}
    with pytest.raises(RemoteAIError):
        _read_verified_result(FakeResponse(headers), expected_request_id=KEY)
