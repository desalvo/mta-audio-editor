"""Cross-process lock for publishing results into the same MTA project.

The lock file is stored in the durable AI queue directory and is never used
as a source of authority; project access is checked by the API beforehand.
"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path

from . import ai_arranger_runtime as runtime

try:
    import fcntl
except ImportError:  # POSIX server only
    fcntl = None


@contextmanager
def project_publication_lock(project_id):
    if fcntl is None:
        raise RuntimeError('Project publication locking requires POSIX flock')
    if not isinstance(project_id, str) or not project_id or len(project_id) > 256:
        raise ValueError('Invalid project identifier')
    runtime._ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(project_id.encode('utf-8')).hexdigest()
    path = runtime._ROOT / ('project-publication-' + key + '.lock')
    if path.is_symlink():
        raise RuntimeError('Unsafe project lock path')
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'a+b') as handle:
        os.fchmod(handle.fileno(), 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
