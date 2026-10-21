"""Directory durability boundary shared by media publication and recovery.

Python's POSIX os.open/fsync directory sequence fails with EACCES on Windows.
On Windows, callers still MUST flush/fsync file contents before os.replace;
this helper does not claim POSIX directory-fsync power-loss guarantees there.
On POSIX failures propagate, so a failed flush cannot retire a recovery journal.
"""
import os


def sync_directory(path):
    if os.name == 'nt':
        return
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
