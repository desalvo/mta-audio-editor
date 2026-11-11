"""Explicit local BS RoFormer installation from fixed, verified upstream sources.

Nothing is downloaded until an administrator starts a job. The installed
runtime is versioned and activated only after checkpoint and model validation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

from .ai_execution_policy import isolated_env
from .bass_roformer_runtime import CHECKPOINT_SHA256, managed_checkpoint

COMMIT = 'ea7eb9c20ea0e3f94368a30fc1654b51cdd55789'
REPOSITORY = 'https://github.com/ZFTurbo/Music-Source-Separation-Training.git'
RELEASE = 'https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v1.0.12/'
CONFIG = ('config_bs_roformer_384_8_2_485100.yaml', 4566,
          'd8afb980318d0c08b9c2e24a7adc00d4f3150320c127a7e4de861800d1321939')
WEIGHTS = ('model_bs_roformer_ep_17_sdr_9.6568.ckpt', 527385512, CHECKPOINT_SHA256)
DEPENDENCIES = ('numpy==1.26.4', 'scipy==1.13.1', 'soundfile==0.12.1', 'librosa==0.10.2',
                'tqdm==4.67.1', 'matplotlib==3.9.4', 'ml-collections==1.1.0',
                'omegaconf==2.2.3', 'wandb==0.19.11', 'loralib==0.1.2',
                'beartype==0.22.5', 'rotary-embedding-torch==0.3.5', 'einops==0.8.1')
TEST = '''import sys,torch
expected=sys.argv[4]
backend='rocm' if torch.version.hip else ('cuda' if torch.version.cuda else 'cpu')
if expected not in ('cpu','cuda','rocm') or backend!=expected:
    raise RuntimeError('BS RoFormer PyTorch backend mismatch: expected '+expected+', got '+backend)
device='cpu'
if expected!='cpu':
    if not torch.cuda.is_available():
        raise RuntimeError('BS RoFormer selected accelerator is unavailable: '+expected)
    device='cuda:0'
# Exercise a kernel, transfer and synchronization, not just driver discovery.
sample=torch.ones((16,16),device=device)
result=sample@sample
if expected!='cpu': torch.cuda.synchronize()
if not torch.isfinite(result).all().item() or not torch.allclose(result,torch.full_like(result,16)):
    raise RuntimeError('BS RoFormer device computation validation failed')
sys.path.insert(0,sys.argv[1])
from utils.settings import get_model_from_config
model,config=get_model_from_config('bs_roformer',sys.argv[2])
state=torch.load(sys.argv[3],map_location='cpu',weights_only=True)
for key in ('state','state_dict','model_state_dict'):
    if key in state: state=state[key]
model.load_state_dict(state,strict=True)
assert list(config.training.instruments)==['drums','bass','other','vocals']
model.to(device)
if expected!='cpu': torch.cuda.synchronize()
print('BS RoFormer strict model load and device validation passed: '+expected)
'''


def root():
    return managed_checkpoint().parent


def selected_device(value):
    if value != 'auto': return value
    if Path('/dev/kfd').exists() and list(Path('/dev/dri').glob('renderD*')): return 'rocm'
    return 'cuda' if Path('/dev/nvidiactl').exists() else 'cpu'


def torch_arguments(device):
    if device == 'rocm':
        return ['torch==2.11.0+rocm7.2', 'torchaudio==2.11.0+rocm7.2',
                'torchvision==0.26.0+rocm7.2', '--index-url', 'https://download.pytorch.org/whl/rocm7.2']
    if device == 'cpu':
        return ['torch==2.11.0+cpu', 'torchaudio==2.11.0+cpu',
                'torchvision==0.26.0+cpu', '--index-url', 'https://download.pytorch.org/whl/cpu']
    return ['torch==2.11.0+cu128', 'torchaudio==2.11.0+cu128', 'torchvision==0.26.0+cu128',
            '--index-url', 'https://download.pytorch.org/whl/cu128']


def receipt():
    path = root() / 'runtime.json'
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        return None
    try:
        value = json.loads(path.read_text())
        ident = value.get('id', '')
        if value.get('commit') != COMMIT or not re.fullmatch('[a-f0-9]{32}', ident):
            return None
        directory = root() / 'runtimes' / ident
        if any(p.is_symlink() for p in (root(), root() / 'runtimes', directory)):
            return None
        source, config, python = directory / 'source', directory / CONFIG[0], directory / ('venv/Scripts/python.exe' if os.name == 'nt' else 'venv/bin/python')
        if (source.is_symlink() or config.is_symlink() or python.is_symlink()
                or not (source / 'inference.py').is_file() or not config.is_file() or not python.is_file()
                or config.stat().st_size != CONFIG[1] or hashlib.sha256(config.read_bytes()).hexdigest() != CONFIG[2]):
            return None
        return {'root': source, 'config': config, 'python': python, 'id': ident,
                'checkpoint_validated': bool(value.get('checkpoint_validated')), 'device': value.get('device','auto'),
                'device_validated': value.get('device_validated') is True}
    except (OSError, ValueError, TypeError):
        return None


def _download(spec, destination, cancelled, progress):
    from .secure_https import https_urlopen
    name, expected_size, expected_hash = spec
    digest = hashlib.sha256(); count = 0
    with https_urlopen(RELEASE + name, timeout=90) as response, destination.open('xb') as out:
        while True:
            if cancelled(): raise RuntimeError('BS RoFormer installation cancelled')
            block = response.read(1024 * 1024)
            if not block: break
            count += len(block)
            if count > expected_size: raise ValueError('BS RoFormer download exceeds expected size')
            digest.update(block); out.write(block)
            progress('downloading-' + ('checkpoint' if spec == WEIGHTS else 'configuration'), count, expected_size)
    if count != expected_size or digest.hexdigest() != expected_hash:
        raise ValueError('BS RoFormer download failed size or SHA-256 verification')


def _run(command, cwd, cancelled, progress, phase):
    from .studio_compute import terminate
    progress(phase, None, None)
    env = isolated_env({**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
                        'GIT_TERMINAL_PROMPT': '0', 'PYTHONNOUSERSITE': '1',
                        'PIP_CONFIG_FILE': os.devnull, 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
                        'WANDB_MODE': 'disabled'})
    with (root() / 'installation.log').open('ab') as log:
        process = subprocess.Popen(list(map(str, command)), cwd=str(cwd), env=env,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=(os.name == 'posix'))
        deadline = time.monotonic() + 3600
        try:
            while process.poll() is None:
                if cancelled(): raise RuntimeError('BS RoFormer installation cancelled')
                if time.monotonic() > deadline: raise RuntimeError('BS RoFormer installation timed out')
                time.sleep(.2)
            if process.returncode:
                raise RuntimeError('BS RoFormer installation failed during ' + phase + '; inspect installation log')
        finally:
            terminate(process)
            process.wait()


def install(device, cancelled, progress, job_id=None):
    from . import model_asset_admin
    from .ai_project_lock import project_publication_lock
    from .ai_worker_registry import worker_python
    from .storage import _atomic_json_write
    if device not in ('auto', 'cpu', 'cuda', 'rocm'): raise ValueError('Invalid accelerator')
    device = selected_device(device)
    if any(os.getenv(name) for name in ('MTA_BASS_ROFORMER_ROOT', 'MTA_BASS_ROFORMER_CONFIG',
                                        'MTA_BASS_ROFORMER_PYTHON', 'MTA_BASS_ROFORMER_CHECKPOINT')):
        raise ValueError('Remove the existing BS RoFormer environment overrides before activating a managed runtime')
    git = shutil.which('git')
    if not git: raise RuntimeError('Git is required on the worker for the verified source checkout')
    directory_root = root()
    if directory_root.is_symlink() or directory_root.parent.is_symlink(): raise ValueError('Unsafe model directory')
    directory_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    runtimes = directory_root / 'runtimes'
    if runtimes.is_symlink(): raise ValueError('Unsafe runtime directory')
    runtimes.mkdir(exist_ok=True, mode=0o700)
    with project_publication_lock('bass-roformer-installation'):
        ident = uuid.uuid4().hex
        directory = runtimes / ident
        directory.mkdir(mode=0o700)
        directory_inode = directory.stat().st_ino
        checkpoint_tmp = directory / 'checkpoint'
        published = False
        try:
            src = directory / 'source'
            git_base = [git, '-c', 'core.hooksPath=/dev/null', '-c', 'protocol.file.allow=never']
            _run(git_base + ['init', str(src)], directory, cancelled, progress, 'source-init')
            _run(git_base + ['-C', str(src), 'fetch', '--depth=1', REPOSITORY, COMMIT], directory, cancelled, progress, 'source-download')
            _run(git_base + ['-C', str(src), 'checkout', '--detach', COMMIT], directory, cancelled, progress, 'source-checkout')
            actual = subprocess.check_output(git_base + ['-C', str(src), 'rev-parse', 'HEAD'], text=True,
                                             env=isolated_env(), timeout=30).strip()
            if actual != COMMIT: raise ValueError('BS RoFormer source commit mismatch')
            config = directory / CONFIG[0]
            _download(CONFIG, config, cancelled, progress)
            target = managed_checkpoint()
            if target.is_file() and not target.is_symlink():
                from .bass_roformer_runtime import verify_checkpoint
                verify_checkpoint(target)
                checkpoint = target
            else:
                if target.is_symlink(): raise ValueError('Unsafe managed checkpoint')
                _download(WEIGHTS, checkpoint_tmp, cancelled, progress)
                checkpoint = checkpoint_tmp
            base_python = worker_python('demucs')
            venv = directory / 'venv'; python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            _run([base_python, '-m', 'venv', '--copies', str(venv)], directory, cancelled, progress, 'creating-runtime')
            pip = [python, '-m', 'pip', 'install', '--disable-pip-version-check']
            _run(pip + torch_arguments(device), directory, cancelled, progress, 'installing-pytorch')
            constraints = directory / 'constraints.txt'
            versions = subprocess.check_output([str(python), '-I', '-c',
                'import importlib.metadata as m;print("\\n".join(n+"=="+m.version(n) for n in ("torch","torchaudio","torchvision")))'],
                text=True, env=isolated_env(), timeout=30)
            constraints.write_text(versions)
            _run(pip + ['-c', str(constraints), *DEPENDENCIES], directory, cancelled, progress, 'installing-dependencies')
            _run([python, '-I', '-c', TEST, src, config, checkpoint, device], directory, cancelled, progress, 'strict-model-load')
            if cancelled(): raise RuntimeError('BS RoFormer installation cancelled')
            with model_asset_admin.mutation(job_id):
                if cancelled(): raise RuntimeError('BS RoFormer installation cancelled')
                if checkpoint == checkpoint_tmp: os.replace(checkpoint_tmp, target)
                _atomic_json_write(directory_root / 'runtime.json', {'id': ident, 'commit': COMMIT,
                    'checkpoint_validated': True, 'device': device, 'device_validated': True, 'installed_at': time.time()})
                published = True
            return {'installed': True, 'checkpoint_verified': True, 'model_load_verified': True,
                    'device': device, 'device_validated': True,
                    'inference_tested': False, 'scope': 'local-worker'}
        finally:
            if (not published and not directory.is_symlink() and directory.is_dir()
                    and directory.stat().st_ino == directory_inode):
                shutil.rmtree(directory, ignore_errors=True)


def remove(*, checkpoint, job_id=None):
    from .ai_project_lock import project_publication_lock
    from .model_asset_admin import mutation
    if any(os.getenv(name) for name in ('MTA_BASS_ROFORMER_ROOT', 'MTA_BASS_ROFORMER_CONFIG',
                                        'MTA_BASS_ROFORMER_PYTHON', 'MTA_BASS_ROFORMER_CHECKPOINT')):
        raise ValueError('BS RoFormer is configured externally')
    with project_publication_lock('bass-roformer-installation'), mutation(job_id):
        directory = root()
        if directory.is_symlink() or directory.parent.is_symlink():
            raise ValueError('Unsafe BS RoFormer directory')
        if checkpoint:
            target = managed_checkpoint()
            if target.is_symlink():
                raise ValueError('Unsafe BS RoFormer checkpoint')
            target.unlink(missing_ok=True)
        else:
            state = receipt()
            if not state:
                raise ValueError('Verified managed BS RoFormer runtime not found')
            if not shutil.rmtree.avoids_symlink_attacks:
                raise ValueError('Safe runtime removal unavailable')
            (directory / 'runtime.json').unlink()
            shutil.rmtree(directory / 'runtimes' / state['id'])
        return {'removed':True,'checkpoint':checkpoint}


def install_checkpoint(cancelled, job_id):
    from tempfile import TemporaryDirectory
    from .ai_project_lock import project_publication_lock
    from .model_asset_admin import mutation
    from .model_license_policy import evaluate_model
    from .bass_roformer_runtime import verify_checkpoint
    if os.getenv('MTA_BASS_ROFORMER_CHECKPOINT'):
        raise ValueError('BS RoFormer checkpoint is configured externally')
    evaluate_model('bs-roformer-zfturbo')
    target = managed_checkpoint()
    directory = target.parent
    if directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError('Unsafe BS RoFormer directory')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with project_publication_lock('bass-roformer-installation'), TemporaryDirectory(dir=directory) as temp:
        if target.is_symlink():
            raise ValueError('Unsafe BS RoFormer checkpoint')
        if target.is_file():
            verify_checkpoint(target)
            return {'checkpoint_verified':True}
        staged = Path(temp) / 'checkpoint'
        _download(WEIGHTS, staged, cancelled, lambda *_: None)
        with mutation(job_id):
            evaluate_model('bs-roformer-zfturbo')
            if cancelled():
                raise RuntimeError('BS RoFormer checkpoint installation cancelled')
            os.replace(staged, target)
    return {'checkpoint_verified':True}
