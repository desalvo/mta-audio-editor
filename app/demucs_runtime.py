"""Optional operator-selected Demucs Python; never supplied by HTTP callers."""
from functools import lru_cache
import os
from pathlib import Path
import subprocess


def python_path():
    value=os.getenv('MTA_DEMUCS_PYTHON','').strip()
    if not value:return None
    path=Path(value)
    if not path.is_absolute() or not path.is_file() or not os.access(path,os.X_OK):
        raise ValueError('Invalid administrator-configured Demucs Python')
    return path


@lru_cache(maxsize=8)
def _installed(path,stamp):
    try:
        result=subprocess.run([path,'-c','import demucs.separate'],capture_output=True,timeout=30,check=False)
        return result.returncode==0
    except (OSError,subprocess.TimeoutExpired):return False


def available():
    try:
        path=python_path()
        return bool(path and _installed(str(path),path.stat().st_mtime_ns))
    except (OSError,ValueError):return False


def device_arguments():
    device=os.getenv('MTA_DEMUCS_DEVICE','auto').strip().lower()
    if device not in ('auto','cpu','cuda'):
        raise ValueError('Demucs device must be auto, cpu or cuda (including ROCm)')
    # Demucs auto uses torch.cuda.is_available(), also for AMD ROCm builds.
    return [] if device=='auto' else ['--device',device]
