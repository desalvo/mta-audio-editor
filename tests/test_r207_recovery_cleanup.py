from email.message import Message
from io import BytesIO
from unittest.mock import patch
import pytest

from app import ai_result_cache as cache
from app.ai_remote_client import recover_audio, RemoteAIError


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path))


def test_expired_cache_cleanup_dry_run_and_apply(tmp_path, monkeypatch):
    monkeypatch.setattr(cache.time, 'time', lambda: 1000)
    key = 'test-cache-cleanup-0001'
    assert cache.save(1, key, b'RIFFtest', 'audio/wav', 'job-1')
    assert cache.purge_expired(now=90000) == {'examined': 1, 'expired': 1, 'removed': 0}
    assert cache.load(1, key, 'job-1') == (b'RIFFtest', 'audio/wav')
    assert cache.purge_expired(now=90000, dry_run=False)['removed'] == 1
    assert cache.load(1, key, 'job-1') is None


def test_cleanup_leaves_live_and_malformed_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(cache.time, 'time', lambda: 1000)
    cache.save(1, 'test-cache-cleanup-0002', b'RIFFtest', 'audio/wav', 'job-2')
    (tmp_path / ('a' * 64 + '.json')).write_text('{')
    result = cache.purge_expired(now=1010, dry_run=False)
    assert result['removed'] == 0
    assert result['examined'] == 2


class Response:
    headers = Message()
    def __init__(self):
        self.headers = Message()
        self.headers['Content-Type'] = 'audio/wav'
        self.headers['X-MTA-AI-Job-ID'] = 'job-123'
        self.body = BytesIO(b'RIFFresult')
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self, n): return self.body.read(n)


def test_native_recovery_get_only_no_inference():
    with patch('app.ai_remote_client.https_urlopen', return_value=Response()) as call:
        assert recover_audio('https://mta.example.org', 'secret', 'request-key-123456789') == (b'RIFFresult', 'audio/wav', 'job-123')
    req = call.call_args.args[0]
    assert req.get_method() == 'GET'
    assert '/request-result/request-key-123456789' in req.full_url
    assert req.data is None


def test_native_recovery_network_error_fails_closed():
    from urllib.error import URLError
    with patch('app.ai_remote_client.https_urlopen', side_effect=URLError('network')):
        with pytest.raises(RemoteAIError, match='no local model was started'):
            recover_audio('https://mta.example.org', 'secret', 'request-key-123456789')


def test_failed_post_replays_get_once_without_second_post():
    from urllib.error import URLError
    from app.ai_remote_client import infer_audio
    requests = []

    def response(request, **_):
        requests.append(request)
        if request.get_method() == 'POST':
            raise URLError('connection reset after inference')
        return Response()

    with patch('app.ai_remote_client.https_urlopen', side_effect=response):
        payload, mime, job = infer_audio('https://mta.example.org', 'secret', 'whisper', b'RIFF',
                                         request_id='request-key-123456789')
    assert (payload, mime, job) == (b'RIFFresult', 'audio/wav', 'job-123')
    assert [req.get_method() for req in requests] == ['POST', 'GET']


def test_failed_post_never_retries_inference_if_replay_unavailable():
    from urllib.error import URLError
    from app.ai_remote_client import infer_audio
    requests = []

    def failure(request, **_):
        requests.append(request.get_method())
        raise URLError('offline')

    with patch('app.ai_remote_client.https_urlopen', side_effect=failure):
        with pytest.raises(RemoteAIError, match='no local model was started'):
            infer_audio('https://mta.example.org', 'secret', 'demucs', b'RIFF',
                        request_id='request-key-123456789')
    assert requests == ['POST', 'GET']


def test_cache_supports_json_and_auto_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr(cache.time, 'time', lambda: 1000)
    assert cache.save(1, 'json-cache-request-123', b'{"ok":true}', 'application/json', 'job-json')
    assert cache.load(1, 'json-cache-request-123', 'job-json') == (b'{"ok":true}', 'application/json')
    result = cache.cleanup_if_due(now=90000)
    assert result['removed'] == 1
    assert cache.load(1, 'json-cache-request-123', 'job-json') is None


def test_unsafe_cache_root_symlink(tmp_path, monkeypatch):
    unsafe = tmp_path / 'link'
    unsafe.symlink_to(tmp_path, target_is_directory=True)
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(unsafe))
    with pytest.raises(ValueError, match='Unsafe'):
        cache.save(1, 'test-cache-key-12345', b'RIFF', 'audio/wav', 'job')
