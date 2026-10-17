"""OS-backed file locking on POSIX and Windows; never fall back to no locking.

Windows locks byte zero even for an empty lock file. Lock files remain present
between calls; removing them would allow processes to lock different inodes.
"""
import errno
import os
import stat
import time

try:
    import fcntl as _posix
except ImportError:
    _posix = None
try:
    import msvcrt as _windows
except ImportError:
    _windows = None

LOCK_EX = 2
LOCK_NB = 4
LOCK_UN = 8


def flock(fd, operation):
    if _posix is not None:
        return _posix.flock(fd, operation)
    if _windows is None:
        raise RuntimeError('No supported OS file-lock backend')
    if operation not in (LOCK_EX, LOCK_EX | LOCK_NB, LOCK_UN):
        raise ValueError('Unsupported lock operation')
    if operation == LOCK_UN:
        os.lseek(fd, 0, os.SEEK_SET)
        return _windows.locking(fd, _windows.LK_UNLCK, 1)
    while True:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            return _windows.locking(fd, _windows.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise
            if operation & LOCK_NB:
                raise BlockingIOError(exc.errno, 'File lock already held') from exc
            time.sleep(.05)


def private_mode(fd):
    """Set POSIX owner-only bits where supported; Windows inherits directory ACLs."""
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        raise ValueError('Private file must be regular')
    if hasattr(os, 'fchmod'):
        os.fchmod(fd, 0o600)
