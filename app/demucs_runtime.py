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


def checkpoint_fingerprints(model):
    """Hash the active official HF snapshot used by Demucs 4.1 offline.

    Legacy .th checkpoints are tracked separately by StageCache. Snapshot
    symlinks to HF blobs are normal, but must remain within this repository.
    No model imports or network access are needed to identify cached weights.
    """
    import hashlib
    import re
    if not isinstance(model,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',model):
        raise ValueError('Invalid Demucs model identity')
    home=Path(os.getenv('HF_HOME',str(Path(os.getenv('XDG_CACHE_HOME',str(Path.home()/'.cache')))/'huggingface')))
    hub=Path(os.getenv('HF_HUB_CACHE',str(home/'hub')))
    name=('HTDemucs' if model=='htdemucs' else 'HTDemucs-'+model[9:]
          if model.startswith('htdemucs_') else 'Demucs-'+model)
    repo=hub/('models--adefossez--'+name)
    ref=repo/'refs/main'
    if not ref.exists():return {}
    if repo.is_symlink() or ref.is_symlink() or ref.stat().st_size>128:
        raise ValueError('Unsafe Demucs HF reference')
    revision=ref.read_text().strip()
    if not re.fullmatch('[a-f0-9]{40}',revision):raise ValueError('Invalid Demucs HF revision')
    snapshot=repo/'snapshots'/revision
    if snapshot.is_symlink() or not snapshot.is_dir():raise ValueError('Missing Demucs HF snapshot')
    files=sorted([*snapshot.glob('*.safetensors'),*snapshot.glob('*.yaml')])
    if not files or len(files)>128:raise ValueError('Incomplete/oversized Demucs HF snapshot')
    result={'revision':revision,'device':os.getenv('MTA_DEMUCS_DEVICE','auto')}
    for path in files:
        if not path.resolve().is_relative_to(repo.resolve()) or not path.is_file():
            raise ValueError('Unsafe Demucs HF checkpoint')
        with path.open('rb') as stream:result[path.name]=hashlib.file_digest(stream,'sha256').hexdigest()
    return result
