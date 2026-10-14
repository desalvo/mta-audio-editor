"""A lost HTTP response cannot re-execute or re-bill an adapter job."""
import io
import json
import hashlib
from unittest.mock import patch
from urllib.error import URLError
import pytest
from app import ai_remote_client as client

KEY = 'request-id-0123456789'
URL = 'https://server.example'

class Response:
    def __init__(self, body, headers=None):
        self.buf = io.BytesIO(body)
        self.headers = headers or {}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, n): return self.buf.read(n)


def status(state, job=None):
    return Response(json.dumps({'state': state, 'job_id': job}).encode())


def result():
    data = b'RIFF-recovered'
    return Response(data, {'Content-Type': 'audio/wav', 'X-MTA-AI-Job-ID': 'job-1',
                           'X-MTA-AI-Request-ID': KEY,
                           'X-MTA-AI-Result-SHA256': hashlib.sha256(data).hexdigest()})


def test_status_then_recover_no_post():
    methods = []
    def send(req, **kw):
        methods.append((req.get_method(), req.full_url))
        return status('completed', 'job-1') if 'request-status' in req.full_url else result()
    with patch.object(client, 'https_urlopen', side_effect=send):
        assert client.recover_after_lost_response(URL, 'token', KEY) == (b'RIFF-recovered', 'audio/wav', 'job-1')
    assert [m for m, _ in methods] == ['GET', 'GET']
    assert 'request-status/' in methods[0][1]
    assert 'request-result/' in methods[1][1]


@pytest.mark.parametrize('state', ['admitted', 'failed', 'cancelled'])
def test_not_complete_cannot_reexecute(state):
    methods = []
    def send(req, **kw):
        methods.append(req.get_method())
        return status(state)
    with patch.object(client, 'https_urlopen', side_effect=send):
        with pytest.raises(client.RemoteAIError):
            client.recover_after_lost_response(URL, 'token', KEY)
    assert methods == ['GET']


def test_unreachable_status_never_posts():
    methods = []
    def send(req, **kw):
        methods.append(req.get_method())
        raise URLError('network disconnected')
    with patch.object(client, 'https_urlopen', side_effect=send):
        with pytest.raises(client.RemoteAIError, match='status unavailable'):
            client.recover_after_lost_response(URL, 'token', KEY)
    assert methods == ['GET']


@pytest.mark.parametrize('body', [b'not-json', b'[]', b'{"state":"done"}',
                                     b'{"state":"completed","job_id":null}',
                                     b'{"state":"cancelled","job_id":"job-1"}', b' ' * 4097])
def test_untrusted_status_refused(body):
    with patch.object(client, 'https_urlopen', return_value=Response(body)):
        with pytest.raises(client.RemoteAIError):
            client.remote_request_status(URL, 'token', KEY)


def test_recovered_artifact_digest_still_enforced():
    methods = []
    def send(req, **kw):
        methods.append(req.get_method())
        if 'request-status' in req.full_url:
            return status('completed', 'job-1')
        bad = result()
        bad.headers['X-MTA-AI-Result-SHA256'] = '0'*64
        return bad
    with patch.object(client, 'https_urlopen', side_effect=send):
        with pytest.raises(client.RemoteAIError, match='integrity mismatch'):
            client.recover_after_lost_response(URL, 'token', KEY)
    assert methods == ['GET', 'GET']


def test_cancel_before_recovery_never_contacts_server():
    import threading
    ev = threading.Event(); ev.set()
    with patch.object(client, 'https_urlopen') as opened, patch.object(client, 'cancel_remote_request') as cancel:
        with pytest.raises(client.RemoteAIError, match='cancelled'):
            client.recover_after_lost_response(URL, 'token', KEY, cancel_event=ev)
    opened.assert_not_called()
    cancel.assert_called_once()


def test_recovery_configuration_is_bounded():
    with pytest.raises(ValueError):
        client.recover_after_lost_response(URL, 'token', KEY, max_wait_seconds=float('inf'))
    with pytest.raises(ValueError):
        client.recover_after_lost_response(URL, 'token', KEY, max_wait_seconds=3601)
    with pytest.raises(ValueError):
        client.recover_after_lost_response(URL, 'token', KEY, poll_interval_seconds=0)
