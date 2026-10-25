import multiprocessing
import sqlite3
from pathlib import Path

import pytest

from app.regime_maintenance import maintenance_lock, recover_mirror_exclusively
from app.regime_operation_fence import FenceBlocked


def _hold_lock(path, ready, release):
    with maintenance_lock(Path(path)):
        ready.set()
        release.wait(5)


def test_lock_serializes_processes(tmp_path):
    lock = tmp_path / 'maintenance.lock'
    lock.touch(mode=0o600)
    ctx = multiprocessing.get_context('fork')
    ready, release = ctx.Event(), ctx.Event()
    proc = ctx.Process(target=_hold_lock, args=(str(lock), ready, release))
    proc.start()
    try:
        assert ready.wait(3)
        with pytest.raises(FenceBlocked, match='Another maintenance'):
            with maintenance_lock(lock):
                pass
    finally:
        release.set()
        proc.join(5)
        if proc.is_alive():
            proc.terminate()
            proc.join()
    assert proc.exitcode == 0
    with maintenance_lock(lock):
        pass


def test_reject_symlink(tmp_path):
    lock = tmp_path / 'real'
    lock.touch()
    link = tmp_path / 'link'
    link.symlink_to(lock)
    with pytest.raises(FenceBlocked, match='unsafe'):
        with maintenance_lock(link):
            pass


def test_no_database_creation_on_missing_path(tmp_path):
    lock = tmp_path / 'lock'
    lock.touch()
    missing = tmp_path / 'absent.db'
    with pytest.raises(sqlite3.OperationalError):
        recover_mirror_exclusively(missing, tmp_path / 'regime.json', 't1', lock)
    assert not missing.exists()
