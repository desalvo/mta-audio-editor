"""End-to-end safety contract for native pending request status management."""
import json
import pytest
from app import ai_native_remote_journal as journal
from app import native_ai_routing as routing


def configure(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG', str(tmp_path / 'remote-workers.json'))
    routing.configure('whisper', 'remote', 'https://example.org', 'secret')
    return journal.begin('https://example.org', 'secret', 'whisper', b'RIFFWAVE', {})


def test_pending_metadata_does_not_expose_token_audio_or_input(tmp_path, monkeypatch):
    request_id, pending, fingerprint = configure(tmp_path, monkeypatch)
    entries = journal.list_pending()
    assert len(entries) == 1 and entries[0]['request_id'] == request_id
    assert entries[0]['kind'] == 'whisper' and entries[0]['recoverable']
    assert 'secret' not in json.dumps(entries)
    assert 'RIFFWAVE' not in json.dumps(entries)
    assert journal.read_owned_pending(request_id)['url'] == 'https://example.org'
    assert pending is False


def test_unowned_requests_are_rejected(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='not present'):
        journal.read_owned_pending('a'*32)
    with pytest.raises(ValueError, match='Invalid'):
        journal.read_owned_pending('../invalid')


def test_corrupt_record_is_visible_but_not_queryable(tmp_path, monkeypatch):
    request_id, _, fingerprint = configure(tmp_path, monkeypatch)
    journal._entry(fingerprint).write_text('invalid')
    assert journal.list_pending()[0]['damaged'] is True
    with pytest.raises(ValueError, match='not present'):
        journal.read_owned_pending(request_id)


def test_legacy_entry_is_not_remote_queryable(tmp_path, monkeypatch):
    request_id, _, fingerprint = configure(tmp_path, monkeypatch)
    journal._entry(fingerprint).write_text(json.dumps({'request_id': request_id}))
    assert journal.list_pending()[0]['recoverable'] is False


def test_duplicate_submission_remains_pending_and_complete_removes(tmp_path, monkeypatch):
    request_id, _, fingerprint = configure(tmp_path, monkeypatch)
    request_id_again, existing, fp_again = journal.begin('https://example.org','secret','whisper',b'RIFFWAVE',{})
    assert existing and request_id_again == request_id and fp_again == fingerprint
    journal.finish(fingerprint, request_id)
    assert journal.list_pending() == []


def test_status_endpoint_uses_get_only_and_current_token(tmp_path, monkeypatch):
    from app import main
    request_id, _, fingerprint = configure(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    import app.ai_remote_client as client
    def read_status(url, token, key):
        calls.append((url, token, key))
        return {'state': 'completed'}
    monkeypatch.setattr(client, 'remote_request_status', read_status)
    result = main.native_ai_workers_pending_status(object(), request_id)
    assert result['remote']['state'] == 'completed'
    assert calls == [('https://example.org', 'secret', request_id)]
    assert len(journal.list_pending()) == 1


def test_status_endpoint_rejects_changed_worker_settings(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from app import main
    request_id, _, _ = configure(tmp_path, monkeypatch)
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    routing.configure('whisper', 'local')
    with pytest.raises(HTTPException) as error:
        main.native_ai_workers_pending_status(object(), request_id)
    assert error.value.status_code == 409
    assert journal.list_pending()[0]['request_id'] == request_id
