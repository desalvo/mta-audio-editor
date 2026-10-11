"""Cross-worker adapter execution contract and safe concurrent benchmarking."""
from pathlib import Path
import subprocess
import sys

import pytest

from app import ai_unified_adapter as adapter


def test_rejects_unstaged_audio(tmp_path):
    external = tmp_path / 'external.wav'
    external.write_bytes(b'x')
    with pytest.raises(ValueError, match='staged'):
        adapter.infer({'kind':'whisper', 'source_audio':str(external)}, tmp_path/'preview.wav')


def test_rejects_unlisted_worker(tmp_path):
    (tmp_path/'source.wav').write_bytes(b'dummy')
    with pytest.raises(ValueError, match='Unsupported'):
        adapter.infer({'kind':'arbitrary', 'source_audio':str(tmp_path/'source.wav')}, tmp_path/'preview.wav')


def test_unified_worker_registry_opt_in(monkeypatch):
    from app.ai_worker_registry import resolve_worker
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED','true')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true')
    assert resolve_worker('whisper') == Path(adapter.__file__).resolve()
    monkeypatch.delenv('MTA_AI_UNIFIED_WORKERS_ENABLED')
    assert resolve_worker('whisper') is None


def test_runner_script_imports_in_isolated_folder(tmp_path):
    proc = subprocess.run([sys.executable,str(Path(adapter.__file__).resolve()),'--help'],cwd=tmp_path,capture_output=True,text=True)
    assert proc.returncode == 0


def test_concurrent_wizard_help():
    root = Path(__file__).parents[1]
    proc=subprocess.run(['bash',str(root/'scripts/install_ace_step.sh'),'--benchmark-concurrent'],capture_output=True,text=True)
    assert proc.returncode == 2
    assert 'Missing --benchmark-remote-url' in proc.stderr
