"""Real cancellability of queued/active process-backed web jobs."""
import threading
import time
import pytest
from app import ai_arranger_runtime as queue


def test_running_cancellable_job_receives_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    ready = threading.Event()
    exited = threading.Event()
    def worker(path, cancel_event):
        ready.set()
        assert cancel_event.wait(3)
        exited.set()
        raise RuntimeError('cancelled')
    _, job = queue.start('p', 'arranger', worker, cancellable=True)
    assert ready.wait(5)
    status = queue.cancel(job['job_id'])
    assert status['cancel_requested']
    assert exited.wait(3)
    for _ in range(100):
        status = queue.get(job['job_id'])
        if status['state'] == 'cancelled':
            break
        time.sleep(.02)
    assert status['state'] == 'cancelled'


def test_running_uncancellable_job_is_not_falsely_cancelled(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    ready = threading.Event()
    release = threading.Event()
    def worker(path):
        ready.set()
        release.wait(3)
    _, job = queue.start('p', 'legacy', worker)
    assert ready.wait(5)
    try:
        with pytest.raises(ValueError, match='does not support'):
            queue.cancel(job['job_id'])
    finally:
        release.set()
