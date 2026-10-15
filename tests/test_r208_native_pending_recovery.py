"""Native crash recovery never repeats remote infer or charges after a lost reply."""

import pytest
from app import ai_native_remote_journal as journal
from app import native_ai_routing as routing
from app import ai_remote_client


def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG', str(tmp_path / 'settings.json'))
    routing.configure('whisper', 'remote', 'https://example.org', 'private')
    wav = tmp_path / 'voice.wav'
    wav.write_bytes(b'RIFF\0\0\0\0WAVE')
    return wav


def test_pending_keeps_id_and_never_reposts(tmp_path, monkeypatch):
    wav = setup(tmp_path, monkeypatch)
    calls = []
    def lost(*args, **kwargs):
        calls.append(('post', kwargs['request_id']))
        raise ai_remote_client.RemoteAIError('connection lost')
    monkeypatch.setattr(ai_remote_client, 'infer_audio', lost)
    with pytest.raises(ai_remote_client.RemoteAIError, match='connection lost'):
        routing.infer('whisper', wav)
    def recovered(*args, **kwargs):
        calls.append(('get', args[2]))
        return b'{"text":"ok"}', 'application/json', 'job-1'
    monkeypatch.setattr(ai_remote_client, 'recover_after_lost_response', recovered)
    result, job = routing.infer('whisper', wav)
    assert job == 'job-1' and result['json']['result.json']['text'] == 'ok'
    assert len(calls) == 2 and calls[0][0] == 'post' and calls[1] == ('get', calls[0][1])
    assert not list((tmp_path/'remote-pending').glob('*.json'))


def test_pending_remains_after_failed_recovery(tmp_path, monkeypatch):
    wav = setup(tmp_path, monkeypatch)
    def failed(*args, **kwargs):
        raise ai_remote_client.RemoteAIError('unavailable')
    monkeypatch.setattr(ai_remote_client, 'infer_audio', failed)
    with pytest.raises(ai_remote_client.RemoteAIError): routing.infer('whisper', wav)
    monkeypatch.setattr(ai_remote_client, 'recover_after_lost_response', failed)
    with pytest.raises(ai_remote_client.RemoteAIError): routing.infer('whisper', wav)
    assert len(list((tmp_path/'remote-pending').glob('*.json'))) == 1


def test_corrupt_pending_fails_closed(tmp_path, monkeypatch):
    wav = setup(tmp_path, monkeypatch)
    request_id, _, fingerprint = journal.begin('https://example.org', 'private', 'whisper', wav.read_bytes(), None)
    journal._entry(fingerprint).write_text('INVALID')
    with pytest.raises(RuntimeError, match='damaged'):
        routing.infer('whisper', wav)


def test_separate_inputs_have_distinct_identities(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    x = b'RIFFWAVE'
    first = journal.begin('https://example.org','private','whisper',x,None)
    second = journal.begin('https://example.org','private','whisper',x,{'language':'en'})
    assert first[0] != second[0]
    assert journal.begin('https://example.org','private','whisper',x,None)[:2] == (first[0], True)
