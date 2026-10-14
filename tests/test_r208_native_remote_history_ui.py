"""Native server-backed AI history discovery: read-only, authenticated and token-safe."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from app import main, native_ai_routing, ai_remote_client


def test_native_remote_history_uses_saved_credentials_without_exposing_them(monkeypatch):
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    monkeypatch.setattr(native_ai_routing, '_read', lambda: {'workers': {'whisper': {'mode': 'remote', 'url': 'https://ai.example', 'token': 'secret'}}})
    call = Mock(return_value={'total': 1, 'limit': 10, 'offset': 2, 'items': [{'request_key': 'request-key', 'state':'admitted', 'job_id':None, 'created_at': 1780000000}]})
    monkeypatch.setattr(ai_remote_client, 'list_remote_requests', call)
    result = main.native_ai_workers_remote_history(None, 'whisper', 10, 2)
    call.assert_called_once_with('https://ai.example', 'secret', limit=10, offset=2, state=None)
    assert result['kind'] == 'whisper' and result['total'] == 1
    assert 'secret' not in str(result) and 'https://ai.example' not in str(result)


def test_history_rejects_unconfigured_and_unknown_models(monkeypatch):
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    monkeypatch.setattr(native_ai_routing, '_read', lambda: {'workers': {}})
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_remote_history(None, 'whisper')
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_remote_history(None, 'unknown-model')
    assert exc.value.status_code == 404


def test_remote_errors_do_not_start_inference(monkeypatch):
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    monkeypatch.setattr(native_ai_routing, '_read', lambda: {'workers': {'demucs': {'mode': 'remote', 'url': 'https://ai.example', 'token': 'secret'}}})
    monkeypatch.setattr(ai_remote_client, 'list_remote_requests', lambda *args, **kwargs: (_ for _ in ()).throw(ai_remote_client.RemoteAIError('unavailable')))
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_remote_history(None, 'demucs')
    assert exc.value.status_code == 502


def test_native_history_ui_is_non_inferential():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'app/static/app.js').read_text()
    section = source.split('async function refreshNativeRemoteHistory(){', 1)[1].split('async function refreshNativePending(){', 1)[0]
    assert '/api/native/ai-workers/remote-history/' in section
    assert 'method:\'POST\'' not in section
    assert 'textContent' in section and 'replaceChildren()' in section
