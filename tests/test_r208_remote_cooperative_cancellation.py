import threading
import pytest
from app import ai_remote_client


def test_cancelled_inference_never_contacts_server(monkeypatch):
    evt = threading.Event(); evt.set()
    def fail(*args, **kwargs):
        pytest.fail('network contacted after cancellation')
    monkeypatch.setattr(ai_remote_client, 'https_urlopen', fail)
    with pytest.raises(ai_remote_client.RemoteAIError, match='cancelled'):
        ai_remote_client.infer_audio('https://worker.example', 'token', 'whisper', b'RIFF', cancel_event=evt)


def test_cancelled_recovery_never_contacts_server(monkeypatch):
    evt = threading.Event(); evt.set()
    monkeypatch.setattr(ai_remote_client, 'https_urlopen', lambda *a, **kw: pytest.fail('network contacted'))
    with pytest.raises(ai_remote_client.RemoteAIError, match='cancelled'):
        ai_remote_client.recover_audio('https://worker.example', 'token', 'abc', cancel_event=evt)


def test_cancelled_result_cannot_call_metering_sink():
    evt = threading.Event(); evt.set()
    class Response:
        headers = {}
    with pytest.raises(ai_remote_client.RemoteAIError, match='cancelled'):
        ai_remote_client._read_verified_result(Response(), cancel_event=evt,
            metering_sink=lambda *a: pytest.fail('metering persisted after cancellation'))


def test_cancel_after_result_bytes_prevents_sink():
    evt = threading.Event()
    class Response:
        headers = {'Content-Type': 'audio/wav', 'X-MTA-AI-Job-ID': 'job-1'}
        def read(self, *args):
            evt.set()
            return b'valid'
    with pytest.raises(ai_remote_client.RemoteAIError, match='cancelled'):
        ai_remote_client._read_verified_result(Response(), cancel_event=evt,
            metering_sink=lambda *a: pytest.fail('sink called'))
