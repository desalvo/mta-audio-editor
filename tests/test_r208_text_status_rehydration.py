"""Polling a persisted text/marker job must not restart its inference."""
from app import main


def test_terminal_marker_rehydrates_without_executor(monkeypatch):
    row = {'operation': 'extract-markers', 'project_id': 'project-1',
           'state': 'interrupted', 'message': 'Review needed',
           'created_at': 12.0, 'completed_at': 13.0, 'progress_percent': 48}
    monkeypatch.setattr(main.ai_arranger_runtime, 'get', lambda jid: row)
    monkeypatch.setattr(main.ai_arranger_runtime, 'read_payload', lambda jid: {
        'schema_version': 1, 'kind': 'markers', 'project_id': 'project-1'})
    saved = main._rehydrate_persisted_text_job('marker-123')
    assert saved['status'] == 'interrupted'
    assert saved['progress'] == 48
    assert saved['kind'] == 'extract-markers'


def test_rehydrate_rejects_mismatched_project(monkeypatch):
    monkeypatch.setattr(main.ai_arranger_runtime, 'get', lambda jid: {
        'operation': 'extract-lyrics', 'project_id': 'original', 'state': 'queued'})
    monkeypatch.setattr(main.ai_arranger_runtime, 'read_payload', lambda jid: {
        'schema_version': 1, 'kind': 'lyrics', 'project_id': 'other'})
    assert main._rehydrate_persisted_text_job('different-project') is None
