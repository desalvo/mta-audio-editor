"""Server queue persistence and configurable concurrent admissions."""
from pathlib import Path
from threading import Event
import time

from app import ai_arranger_runtime as queue


def test_two_execution_slots_and_third_waits(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    queue.configure(2)
    gate = Event()
    entered = [Event(), Event()]
    def blocked(index):
        def execute(_path):
            entered[index].set()
            assert gate.wait(8)
        return execute
    first = queue.start('proj-1', 'arranger', blocked(0))[1]
    second = queue.start('proj-2', 'stems', blocked(1))[1]
    try:
        assert entered[0].wait(5)
        assert entered[1].wait(5)
        assert queue.get(first['job_id'])['state'] == 'running'
        assert queue.get(second['job_id'])['state'] == 'running'
        third = queue.start('proj-3', 'lyrics', lambda _: None)[1]
        assert queue.get(third['job_id'])['state'] == 'queued'
        assert queue.get(third['job_id'])['jobs_ahead'] == 0
        assert queue.cancel(third['job_id'])['state'] == 'cancelled'
        assert not (tmp_path / (third['job_id'] + '.progress.json')).exists()
    finally:
        gate.set()
    for _ in range(100):
        if all(queue.get(x['job_id'])['state'] == 'completed' for x in (first, second)):
            break
        time.sleep(0.05)
    assert all(queue.get(x['job_id'])['state'] == 'completed' for x in (first, second))


def test_server_queue_default_is_persistent():
    source = Path(queue.__file__).read_text()
    assert "Path('/var/lib/mta/ai-jobs')" in source
