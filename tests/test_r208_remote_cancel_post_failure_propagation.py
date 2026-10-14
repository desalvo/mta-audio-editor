import threading
from urllib.error import URLError
import pytest
from app import ai_remote_client as client


def test_network_failure_after_cancellation_sends_durable_barrier(monkeypatch):
    event = threading.Event()
    calls = []
    def lost_response(*args, **kwargs):
        event.set()
        raise URLError('lost')
    monkeypatch.setattr(client, 'https_urlopen', lost_response)
    monkeypatch.setattr(client, 'cancel_remote_request', lambda url, token, request_id, **kw: calls.append(request_id))
    with pytest.raises(client.RemoteAIError, match='cancelled'):
        client.infer_audio('https://remote.example', 'token', 'whisper', b'RIFF', request_id='a'*32, cancel_event=event)
    assert calls == ['a'*32]


def test_cancelled_result_attempts_barrier_before_exposing_data(monkeypatch):
    event = threading.Event()
    calls = []
    class Response:
        headers = {'Content-Type':'audio/wav', 'X-MTA-AI-Job-ID':'job-01'}
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, *_):
            event.set()
            return b'RIFF'
    monkeypatch.setattr(client, 'https_urlopen', lambda *args, **kw: Response())
    monkeypatch.setattr(client, 'cancel_remote_request', lambda url, token, request_id, **kw: calls.append(request_id))
    with pytest.raises(client.RemoteAIError, match='cancelled'):
        client.infer_audio('https://remote.example', 'token', 'whisper', b'RIFF', request_id='b'*32, cancel_event=event)
    assert calls == ['b'*32]


def test_failed_barrier_never_claims_remote_stop(monkeypatch):
    event = threading.Event()
    def lost_response(*args, **kwargs):
        event.set()
        raise URLError('lost')
    monkeypatch.setattr(client, 'https_urlopen', lost_response)
    monkeypatch.setattr(client, 'cancel_remote_request', lambda *args, **kwargs: (_ for _ in ()).throw(client.RemoteAIError('unreachable')))
    with pytest.raises(client.RemoteAIError, match='stop not guaranteed'):
        client.infer_audio('https://remote.example', 'token', 'whisper', b'RIFF', request_id='c'*32, cancel_event=event)
