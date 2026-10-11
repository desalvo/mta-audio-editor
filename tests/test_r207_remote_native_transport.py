"""Remote-native transport must not silently fall back to local inference."""
from email.message import Message
from io import BytesIO
from unittest.mock import patch
import pytest
from app.ai_remote_client import infer_audio, RemoteAIError, _endpoint


def test_endpoint_rejects_insecure_or_embedded_credentials():
    for address in ('http://mta.example.com', 'https://user:pass@mta.example.com',
                    'https://mta.example.com/other', 'https://mta.example.com?token=bad'):
        with pytest.raises(ValueError):
            _endpoint(address, 'whisper')
    assert _endpoint('https://mta.example.com/api/ai-gateway', 'whisper').endswith('/api/ai-jobs/execute-audio/whisper')


def test_rejects_arbitrary_worker_and_paths():
    with pytest.raises(ValueError): _endpoint('https://example.com', '../../bin/bash')
    with pytest.raises(ValueError): infer_audio('https://example.com', 'token', 'whisper', b'a', {'command': 'rm'})


class Response:
    def __init__(self, body=b'RIFFdata', media='audio/wav', job='job-1'):
        self.body = BytesIO(body)
        self.headers = Message()
        self.headers['Content-Type'] = media
        if job: self.headers['X-MTA-AI-Job-ID'] = job
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self, n): return self.body.read(n)


def test_remote_success_and_job_identity():
    with patch('app.ai_remote_client.https_urlopen', return_value=Response()) as call:
        result = infer_audio('https://mta.example.com', 'test-token', 'whisper', b'RIFF')
    assert result == (b'RIFFdata', 'audio/wav', 'job-1')
    assert call.call_args.args[0].get_header('Authorization') == 'Bearer test-token'


def test_network_failure_never_starts_local_worker():
    from urllib.error import URLError
    with patch('app.ai_remote_client.https_urlopen', side_effect=URLError('offline')):
        with pytest.raises(RemoteAIError, match='no local model was started'):
            infer_audio('https://mta.example.com', 'test-token', 'demucs', b'RIFF')


def test_oversized_and_unidentified_output_rejected():
    with patch('app.ai_remote_client.https_urlopen', return_value=Response(job='')):
        with pytest.raises(RemoteAIError, match='job identifier'):
            infer_audio('https://mta.example.com', 'test-token', 'whisper', b'RIFF')
