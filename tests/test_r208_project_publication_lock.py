"""Cross-process publication lock must prevent lost project updates."""
import multiprocessing
import time

from app import ai_project_lock


def _hold(project, start, finish, root, delay):
    from pathlib import Path
    from app import ai_arranger_runtime
    ai_arranger_runtime._ROOT = Path(root)
    with ai_project_lock.project_publication_lock(project):
        start.put(time.monotonic())
        time.sleep(delay)
        finish.put(time.monotonic())


def test_project_publication_lock_serializes_processes(tmp_path):
    ctx = multiprocessing.get_context('spawn')
    starts, ends = ctx.Queue(), ctx.Queue()
    processes = [ctx.Process(target=_hold, args=('same-project', starts, ends, str(tmp_path), .25)) for _ in range(2)]
    for p in processes: p.start()
    times = [(starts.get(timeout=10), ends.get(timeout=10)) for _ in processes]
    for p in processes:
        p.join(10)
        assert p.exitcode == 0
    assert times[1][0] >= times[0][1] - .01


def test_project_lock_rejects_bad_id():
    import pytest
    with pytest.raises(ValueError):
        with ai_project_lock.project_publication_lock(''):
            pass


def test_publication_lock_is_reentrant_in_same_thread(tmp_path, monkeypatch):
    from app import ai_arranger_runtime
    monkeypatch.setattr(ai_arranger_runtime, '_ROOT', tmp_path)
    with ai_project_lock.project_publication_lock('nested-project'):
        with ai_project_lock.project_publication_lock('nested-project'):
            assert True


def test_nested_project_lock_does_not_release_outer_lock(tmp_path, monkeypatch):
    import threading
    from app import ai_arranger_runtime
    monkeypatch.setattr(ai_arranger_runtime, '_ROOT', tmp_path)
    entered = threading.Event()
    release = threading.Event()

    def contender():
        with ai_project_lock.project_publication_lock('nested-project'):
            entered.set()
        release.set()

    with ai_project_lock.project_publication_lock('nested-project'):
        with ai_project_lock.project_publication_lock('nested-project'):
            pass
        thread = threading.Thread(target=contender, daemon=True)
        thread.start()
        assert not entered.wait(0.15)
    assert release.wait(2)
    thread.join(2)
