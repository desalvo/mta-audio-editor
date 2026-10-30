import pytest
from app.ai_worker_registry import resolve_worker, available_workers, WORKER_KINDS


def test_all_known_model_families_have_registry_entries():
    assert {'ace-step', 'whisper', 'demucs', 'sam-audio', 'drumsep', 'chords-ml', 'remix'} <= WORKER_KINDS


def test_unknown_kind_fails_closed():
    with pytest.raises(ValueError):
        resolve_worker('../bin/sh')
    with pytest.raises(ValueError):
        resolve_worker('arbitrary-command')


def test_per_kind_opaque_admin_configuration_is_unavailable(monkeypatch, tmp_path):
    worker = tmp_path / 'whisper.py'
    worker.write_text('#!/usr/bin/env python3\n')
    worker.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_EXECUTABLE', str(worker))
    assert resolve_worker('whisper') is None
    assert resolve_worker('demucs') is None
    assert available_workers()['whisper'] is False
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_EXECUTABLE', '/bin/does-not-exist')
    assert resolve_worker('whisper') is None


def test_symlink_is_rejected(monkeypatch, tmp_path):
    real = tmp_path / 'real'
    real.write_text('ok')
    real.chmod(0o700)
    link = tmp_path / 'link'
    link.symlink_to(real)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_DEMUCS_EXECUTABLE', str(link))
    assert resolve_worker('demucs') is None
