import tempfile
import time
from pathlib import Path
from threading import Event

from app import ai_arranger_runtime as q


def test_fifo_limit_position_cancel_and_reorder(monkeypatch):
    with tempfile.TemporaryDirectory() as path:
        monkeypatch.setattr(q, '_ROOT', Path(path))
        entered = Event()
        release = Event()
        def blocked(_):
            entered.set()
            release.wait(8)
        a = q.start('a', 'arranger', blocked)[1]
        assert entered.wait(4)
        b = q.start('b', 'arranger', lambda _: None)[1]
        c = q.start('c', 'arranger', lambda _: None)[1]
        assert q.get(c['job_id'])['jobs_ahead'] == 1
        q.move(c['job_id'], 1)
        assert q.get(c['job_id'])['jobs_ahead'] == 0
        assert q.cancel(b['job_id'])['state'] == 'cancelled'
        release.set()
        for _ in range(80):
            if q.get(c['job_id'])['state'] == 'completed':
                break
            time.sleep(.05)
        assert q.get(c['job_id'])['state'] == 'completed'
        assert q.get(a['job_id'])['state'] == 'completed'


def test_settings_are_persistent(monkeypatch):
    with tempfile.TemporaryDirectory() as path:
        monkeypatch.setattr(q, '_ROOT', Path(path))
        assert q._limit() == 1
        q.configure(3)
        assert q._limit() == 3
        try:
            q.configure(0)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid concurrency allowed')
