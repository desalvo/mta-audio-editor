"""Cross-process lock for publishing results into the same MTA project.

The lock file is stored in the durable AI queue directory and is never used
as a source of authority; project access is checked by the API beforehand.
"""
from contextlib import contextmanager
import hashlib
import os
import threading


from . import ai_arranger_runtime as runtime

from . import platform_file_lock as fcntl


_HELD = threading.local()


@contextmanager
def project_publication_lock(project_id):
    if not isinstance(project_id, str) or not project_id or len(project_id) > 256:
        raise ValueError('Invalid project identifier')
    runtime._ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(project_id.encode('utf-8')).hexdigest()
    path = runtime._ROOT / ('project-publication-' + key + '.lock')
    # A nested publication from the same thread (e.g. sample-editor commit)
    # must reuse its existing flock rather than deadlocking on a second FD.
    held = getattr(_HELD, 'paths', None)
    if held is None:
        held = set()
        _HELD.paths = held
    identity = str(path)
    if identity in held:
        yield
        return
    if path.is_symlink():
        raise RuntimeError('Unsafe project lock path')
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'a+b') as handle:
        fcntl.private_mode(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        held.add(identity)
        try:
            yield
        finally:
            held.remove(identity)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
