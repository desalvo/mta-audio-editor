"""No-journal recovered JSON/stems use the existing validation and publication pipelines."""
from pathlib import Path
from app import main


def test_discovered_routes_are_registered():
    routes = {getattr(route, 'path', '') for route in main.app.routes}
    assert '/api/native/ai-workers/remote-history/{kind}/import-json/{request_id}/{pid}' in routes
    assert '/api/native/ai-workers/remote-history/{kind}/import-stems/{request_id}/{pid}' in routes


def test_wrappers_forward_verified_worker_kind(monkeypatch):
    seen = []
    def json_import(request, request_id, pid, _discovered_kind=None):
        seen.append(('json', request_id, pid, _discovered_kind))
        return {'ok': True}
    def stem_import(request, request_id, pid, _discovered_kind=None):
        seen.append(('stems', request_id, pid, _discovered_kind))
        return {'ok': True}
    monkeypatch.setattr(main, 'native_ai_workers_import_recovered_json', json_import)
    monkeypatch.setattr(main, 'native_ai_workers_import_recovered_stems', stem_import)
    key = 'a' * 32
    assert main.native_ai_workers_import_discovered_json(None, 'whisper', key, 'project')['ok']
    assert main.native_ai_workers_import_discovered_stems(None, 'demucs', key, 'project')['ok']
    assert seen == [('json', key, 'project', 'whisper'), ('stems', key, 'project', 'demucs')]


def test_browser_exposes_structured_import_with_explicit_confirmation():
    js = (Path(__file__).resolve().parents[1] / 'app/static/app.js').read_text()
    handler = js.split('async function importNativeDiscoveredResult(', 1)[1].split('async function testAiArrangerWorker(', 1)[0]
    assert 'confirm(' in handler
    assert "method:'POST'" in handler
    assert 'current?.id' in handler
    assert "import-${format}" in handler
