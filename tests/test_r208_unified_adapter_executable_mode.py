"""Prevent shipping the opt-in unified AI worker without its executable bit."""
import os
from pathlib import Path

import pytest

from app import ai_unified_adapter
from app.ai_worker_registry import resolve_worker


@pytest.mark.skipif(os.name == 'nt', reason='POSIX executable permission gate')
def test_unified_worker_file_is_executable(monkeypatch):
    adapter = Path(ai_unified_adapter.__file__).resolve()
    assert adapter.is_file()
    assert os.access(adapter, os.X_OK), 'ai_unified_adapter.py must be committed as mode 100755'
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.delenv('MTA_AI_WORKER_WHISPER_EXECUTABLE', raising=False)
    assert resolve_worker('whisper') == adapter
