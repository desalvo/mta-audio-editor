"""Serialize preview creation and publish only completed WAV files.

Renderer calls are blocking backend operations; never use this on an audio callback.
"""
import os
import tempfile
import threading
import wave
from pathlib import Path
from typing import Callable

_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}

def publish_wav_preview(destination: Path, render: Callable[[Path], None]) -> bool:
    """Create a valid WAV once per cache key; return whether rendering happened.

    Existing malformed/partial cache files are rejected. The renderer receives
    a sibling temporary filename, and the destination is replaced atomically.
    Concurrent requests for the same key share a lock within this process.
    """
    destination = Path(destination)
    key = str(destination.resolve())
    with _locks_guard:
        lock = _locks.setdefault(key, threading.Lock())
    try:
        with lock:
            if _valid_wav(destination):
                return False
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp = None
            try:
                with tempfile.NamedTemporaryFile(prefix=f".{destination.stem}.", suffix=".wav", dir=destination.parent, delete=False) as file:
                    temp = Path(file.name)
                render(temp)
                if not _valid_wav(temp):
                    raise RuntimeError("Preview renderer produced invalid WAV audio")
                os.replace(temp, destination)
                temp = None
                return True
            finally:
                if temp is not None:
                    temp.unlink(missing_ok=True)
    finally:
        # Keep lock references stable for concurrent waiters; bounded by the
        # process lifetime, just like the process-local preview cache.
        pass

def _valid_wav(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= 44:
            return False
        with wave.open(str(path), "rb") as stream:
            return (stream.getnchannels() in (1, 2)
                    and stream.getframerate() > 0
                    and stream.getnframes() > 0)
    except (OSError, ValueError, EOFError, wave.Error):
        return False
