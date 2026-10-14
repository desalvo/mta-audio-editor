"""Cross-process publication lock must prevent lost project updates."""
import multiprocessing
import time

from app import ai_arranger_runtime, ai_project_lock


def _hold(project, start, finish, root, delay):
    from pathlib import Path
    from app import ai_arranger_runtime, ai_project_lock
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
