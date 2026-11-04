"""Local lifecycle for the isolated shared audio runtime installed by MTA."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

from .ai_adapter_identity import MANAGED_RUNTIME_OWNER, MANAGED_RUNTIME_ROOT, require_worker_interpreter
from .ai_install_catalog import ENGINE_GROUPS

AUDIO_KINDS = frozenset(kind for kind, group in ENGINE_GROUPS.items() if group == 'audio')


def _installer():
    source = Path(__file__).resolve().parent.parent
    for name in ('native-installers/install_ai_engines.py', 'scripts/install_ai_engines.py'):
        path = source / name
        if path.is_file() and not path.is_symlink():
            return path
    return None


def _receipt():
    return MANAGED_RUNTIME_ROOT / '.mta-web-audio.json'


def _state():
    if sys.platform != 'linux' or os.getenv('MTA_NATIVE_SINGLE_USER', '').lower() == 'true':
        return None
    path = _receipt()
    if not path.exists() and not path.is_symlink():
        return None
    info = path.lstat()
    if path.is_symlink() or not path.is_file() or info.st_uid != MANAGED_RUNTIME_OWNER or info.st_mode & 0o022 or info.st_size > 1024:
        raise ValueError('Unsafe managed AI runtime receipt')
    data = json.loads(path.read_text())
    if data == {'enabled': False}:
        return data
    if (not isinstance(data, dict) or set(data) != {'enabled', 'generation'} or data['enabled'] is not True
            or not isinstance(data['generation'], str) or not re.fullmatch(r'[0-9a-f]{16}', data['generation'])):
        raise ValueError('Invalid managed AI runtime receipt')
    return data


def override(kind):
    """Return (managed Python, disabled). Existing operator configuration is the default."""
    if kind not in AUDIO_KINDS:
        return None, False
    state = _state()
    if state is None:
        return None, False
    if not state['enabled']:
        return None, True
    binary = MANAGED_RUNTIME_ROOT / ('ai-' + state['generation']) / 'audio/bin/python'
    return require_worker_interpreter(str(binary), kind), False


def status():
    state = _state()
    installer = _installer()
    from . import ai_pull_coordinator
    local = ai_pull_coordinator.mode() != 'pull'
    writable = sys.platform == 'linux' and os.geteuid() == MANAGED_RUNTIME_OWNER and (
        os.access(MANAGED_RUNTIME_ROOT, os.W_OK) if MANAGED_RUNTIME_ROOT.is_dir()
        else os.access(MANAGED_RUNTIME_ROOT.parent, os.W_OK))
    return {'id': 'audio', 'managed': bool(state and state['enabled']),
            'disabled': bool(state and not state['enabled']), 'can_install': bool(local and writable and installer),
            'can_remove': bool(local and writable and (installer or state) and (state is None or state['enabled'])),
            'engines': sorted(AUDIO_KINDS), 'scope': 'local-server' if local else 'remote-worker'}


def _run(command, cancelled):
    from .ai_execution_policy import isolated_env
    from .studio_compute import terminate
    env = isolated_env({**os.environ, 'PIP_CONFIG_FILE': os.devnull, 'PIP_DISABLE_PIP_VERSION_CHECK': '1'})
    with (MANAGED_RUNTIME_ROOT / '.mta-web-audio-install.log').open('ab') as log:
        process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 3600
        try:
            while process.poll() is None:
                if cancelled() or time.monotonic() >= deadline:
                    raise RuntimeError('Audio runtime installation interrupted or timed out')
                time.sleep(.2)
            if process.returncode:
                raise RuntimeError('Audio runtime installation failed. Check the local audio installation log.')
        finally:
            terminate(process)
            process.wait()


def install(device, cancelled, job_id):
    from .ai_project_lock import project_publication_lock
    from .model_asset_admin import mutation
    from .storage import _atomic_json_write
    if not status()['can_install']:
        raise ValueError('The local server cannot provision this runtime')
    with project_publication_lock('web-audio-runtime'):
        if status()['managed']:
            return
        root = MANAGED_RUNTIME_ROOT
        root.mkdir(mode=0o755, exist_ok=True)
        info = root.lstat()
        if root.is_symlink() or info.st_uid != MANAGED_RUNTIME_OWNER or info.st_mode & 0o022:
            raise ValueError('Unsafe local AI runtime root')
        generation = uuid.uuid4().hex[:16]
        folder = root / ('ai-' + generation)
        folder.mkdir(mode=0o755)
        published = False
        try:
            _run([sys.executable, '-I', str(_installer()), '--runtime-only', generation, '--device', device], cancelled)
            require_worker_interpreter(str(folder / 'audio/bin/python'), 'whisper')
            with mutation(job_id):
                if cancelled():
                    raise RuntimeError('Audio runtime installation cancelled')
                _atomic_json_write(_receipt(), {'enabled': True, 'generation': generation})
                published = True
        finally:
            if not published:
                shutil.rmtree(folder)


def remove(job_id=None):
    from .ai_project_lock import project_publication_lock
    from .model_asset_admin import mutation
    from .storage import _atomic_json_write
    if not status()['can_remove']:
        raise ValueError('The local server cannot remove this runtime')
    with project_publication_lock('web-audio-runtime'), mutation(job_id):
        state = _state()
        if state and not state['enabled']:
            return
        root = MANAGED_RUNTIME_ROOT
        root.mkdir(mode=0o755, exist_ok=True)
        info = root.lstat()
        if root.is_symlink() or info.st_uid != MANAGED_RUNTIME_OWNER or info.st_mode & 0o022:
            raise ValueError('Unsafe local AI runtime root')
        if state and state['enabled']:
            folder = root / ('ai-' + state['generation'])
            require_worker_interpreter(str(folder / 'audio/bin/python'), 'whisper')
            if not shutil.rmtree.avoids_symlink_attacks:
                raise ValueError('Safe runtime removal unavailable')
            # Disable dispatch before removing managed files. Operator-installed
            # runtimes have no receipt and remain outside this deletion scope.
            _atomic_json_write(_receipt(), {'enabled': False})
            shutil.rmtree(folder)
        else:
            _atomic_json_write(_receipt(), {'enabled': False})
