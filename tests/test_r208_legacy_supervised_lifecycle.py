

import threading


import pytest

from app.ai_worker_protocol import WorkerUnavailable, run_external_worker


def _worker(tmp_path, monkeypatch, body):
    path = tmp_path / 'worker.py'
    path.write_text('#!/usr/bin/env python3\n' + body)
    path.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_EXECUTABLE', str(path))
    return path


def test_legacy_worker_precancel_skips_execution(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    marker = tmp_path / 'started'
    _worker(tmp_path, monkeypatch, f'from pathlib import Path\nPath({str(marker)!r}).write_text("started")\n')
    event = threading.Event()
    event.set()
    with pytest.raises(WorkerUnavailable, match='cancelled'):
        run_external_worker({'prompt': 'hello'}, timeout_seconds=2, cancel_event=event)
    assert not marker.exists()


def test_legacy_worker_cancel_running(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    marker = tmp_path / 'started'
    _worker(tmp_path, monkeypatch, f'from pathlib import Path\nimport time\nPath({str(marker)!r}).write_text("started")\ntime.sleep(15)\n')
    event = threading.Event()
    import threading as _threading
    def cancel_on_start():
        assert _threading.Event().wait(0.05) is False
        for _ in range(100):
            if marker.exists():
                event.set()
                return
            _threading.Event().wait(0.01)
        event.set()
    thread = threading.Thread(target=cancel_on_start)
    thread.start()
    try:
        with pytest.raises(WorkerUnavailable, match='cancelled'):
            run_external_worker({'prompt': 'hello'}, timeout_seconds=3, cancel_event=event)
    finally:
        thread.join(timeout=3)


def test_legacy_worker_timeout(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    _worker(tmp_path, monkeypatch, 'import time\ntime.sleep(15)\n')
    with pytest.raises(WorkerUnavailable, match='timed out'):
        run_external_worker({'prompt': 'hello'}, timeout_seconds=1)


def test_legacy_worker_failed_exit(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    _worker(tmp_path, monkeypatch, 'raise SystemExit(7)\n')
    with pytest.raises(WorkerUnavailable, match='unsuccessfully'):
        run_external_worker({'prompt': 'hello'}, timeout_seconds=2)
