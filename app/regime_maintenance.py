"""POSIX cross-process maintenance lease for offline regime cutover recovery.

The flock is local-host only: multi-host deployments must also quiesce all
replicas via an external orchestrator. It is never a replacement for the
SQLite admission fence or payment reconciliation.
"""
from __future__ import annotations

import fcntl
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .regime_operation_fence import FenceBlocked


@contextmanager
def maintenance_lock(path: Path):
    """Hold a nonblocking exclusive lock on a preexisting, regular file."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise FenceBlocked('Maintenance lock file missing or unsafe')
    flags = os.O_RDWR | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        import stat
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            raise FenceBlocked('Unsafe maintenance lock inode')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise FenceBlocked('Another maintenance operation holds the lock') from exc
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def recover_mirror_exclusively(db_path: Path, mirror_path: Path,
                               transition_id: str, lock_path: Path) -> dict:
    """Perform offline mirror recovery with OS lock and SQLite write lock.

    All application replicas must be stopped or independently fenced before
    invocation. Never releases the service-regime operation fence.
    """
    from .regime_cutover_recovery import recover_committed_mirror

    with maintenance_lock(lock_path):
        connection = sqlite3.connect(f'file:{Path(db_path).resolve()}?mode=rw', uri=True, timeout=0)
        try:
            connection.execute('BEGIN IMMEDIATE')
            try:
                result = recover_committed_mirror(connection, mirror_path=Path(mirror_path),
                                                  transition_id=transition_id)
                connection.commit()
                return result
            except BaseException:
                connection.rollback()
                raise
        finally:
            connection.close()


def finalize_cutover_exclusively(db_path: Path, mirror_path: Path,
                                transition_id: str, lock_path: Path,
                                readiness_check) -> dict:
    """Finalize a pre-committed/mirrored cutover during exclusive offline maintenance.

    A caller-provided authorization must independently certify quiescence of ALL
    provider/webhook/worker entry points. This function does not claim that a
    local flock can fence remote Kubernetes replicas. Never call from HTTP.
    """
    from .regime_balance_continuity import finalize_preserving_balances

    if not callable(readiness_check):
        raise FenceBlocked('Authoritative readiness callback required')
    with maintenance_lock(lock_path):
        connection = sqlite3.connect(f'file:{Path(db_path).resolve()}?mode=rw',
                                     uri=True, timeout=0)
        try:
            connection.execute('BEGIN IMMEDIATE')
            try:
                # A caller-provided callback is never sufficient authorization:
                # the database itself currently reports incomplete coverage of
                # distributed workers and payment provider obligations.
                from .regime_reconciliation import combined_readiness
                from .regime_operation_fence import inspect
                state = inspect(connection)
                report = combined_readiness(connection, current=state['regime'],
                                            target=state['regime'])
                if (report.get('ready_for_automatic_transition') is not True or
                        report.get('unresolved') or
                        report.get('fence', {}).get('all_entry_points_instrumented') is not True):
                    raise FenceBlocked('Provider and worker entry coverage is not authoritatively verified')
                result = finalize_preserving_balances(connection, mirror_path=Path(mirror_path),
                                          transition_id=transition_id,
                                          readiness_check=readiness_check)
                connection.commit()
                return result
            except BaseException:
                connection.rollback()
                raise
        finally:
            connection.close()
