"""Read-only download for authenticated server-discovered requests."""
from unittest.mock import Mock
from fastapi import HTTPException
import pytest
from app import main, native_ai_routing, ai_remote_client

KEY = 'request-key-1234567890'


def setup(monkeypatch):
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    monkeypatch.setattr(native_ai_routing, '_read', lambda: {'workers': {'whisper': {
        'mode': 'remote', 'url': 'https://ai.example', 'token': 'secret'}}})


def test_discovered_download_reuses_existing_result_without_inference(monkeypatch):
    setup(monkeypatch)
    status = Mock(return_value={'state': 'completed', 'job_id': 'job-1'})
    recover = Mock(return_value=(b'{}', 'application/json', 'job-1'))
    monkeypatch.setattr(ai_remote_client, 'remote_request_status', status)
    monkeypatch.setattr(ai_remote_client, 'recover_after_lost_response', recover)
    result = main.native_ai_workers_discovered_artifact(None, 'whisper', KEY)
    assert result.body == b'{}' and result.media_type == 'application/json'
    assert result.headers['cache-control'] == 'no-store'
    recover.assert_called_once()
    status.assert_called_once_with('https://ai.example', 'secret', KEY)


def test_unknown_or_incomplete_discovered_key_cannot_download(monkeypatch):
    setup(monkeypatch)
    recover = Mock()
    monkeypatch.setattr(ai_remote_client, 'recover_after_lost_response', recover)
    monkeypatch.setattr(ai_remote_client, 'remote_request_status', lambda *a, **kw: {'state': 'admitted'})
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_discovered_artifact(None, 'whisper', KEY)
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_discovered_artifact(None, 'whisper', 'bad')
    assert exc.value.status_code == 400
    recover.assert_not_called()


def test_remote_history_download_ui_never_imports_without_receipt():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/'app/static/app.js').read_text()
    block=source.split('async function downloadNativeDiscoveredArtifact(',1)[1].split('async function refreshNativePending()',1)[0]
    assert '/api/native/ai-workers/remote-history/' in block
    assert 'method:\'POST\'' not in block
    assert '/import-' not in block


def test_old_completed_request_does_not_require_history_pagination(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(ai_remote_client, 'list_remote_requests', lambda *a, **kw: pytest.fail('history scan forbidden'))
    monkeypatch.setattr(ai_remote_client, 'remote_request_status', lambda *a, **kw: {'state': 'completed', 'job_id': 'job-1'})
    monkeypatch.setattr(ai_remote_client, 'recover_after_lost_response', lambda *a, **kw: (b'RIFF', 'audio/wav', 'job-1'))
    assert main.native_ai_workers_discovered_artifact(None, 'whisper', KEY).body == b'RIFF'
