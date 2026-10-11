"""Opt-in desktop ACE-Step installation and local server control.

No shell downloads or execution of downloaded code without user consent. uv and
Git must already be trusted local programs. Installer manages its own directory.
"""
from __future__ import annotations
import os
import json
import signal
from pathlib import Path
from urllib.parse import urlsplit
import shutil
import subprocess
import threading
import uuid
import re
import time

SOURCE = 'https://github.com/ACE-Step/ACE-Step-1.5.git'
_LOCK = threading.RLock()
_TASK: dict = {'state': 'idle'}
_PROCESS: subprocess.Popen | None = None
_CACHE_BASELINE = 0



def home() -> Path:
    return Path(os.environ.get('MTA_ACE_STEP_DESKTOP_DIR', str(Path.home()/'.local'/'share'/'mta-audio-editor'/'ace-step'))).expanduser().resolve()


def status() -> dict:
    folder = home()/'source'
    with _LOCK:
        task = dict(_TASK)
        running = _PROCESS is not None and _PROCESS.poll() is None
    if running:
        size = _cache_size(home()/'models')
        task.setdefault('phase', 'model_initialization')
        task['model_cache_bytes'] = size
        task['model_downloaded_bytes_this_session'] = max(0, size - _CACHE_BASELINE)
        task.setdefault('progress_percent', None)  # ACE-Step does not expose total model bytes.
    return {'task':task,'auto_start_enabled':_consent_file().is_file(),'installed':(folder/'pyproject.toml').is_file() and (folder/'.venv').is_dir(),
            'server_running':running,'has_git':bool(shutil.which('git')),'has_uv':bool(shutil.which('uv')),
            'model_cache':str(home()/'models')}


def _connection_file() -> Path:
    return home() / 'connection.json'


def connection() -> dict:
    """Return public connection preferences; never expose saved credentials."""
    try:
        cfg = json.loads(_connection_file().read_text(encoding='utf-8'))
        if cfg.get('mode') in ('local', 'remote'):
            return {'configured': True, 'mode': cfg['mode'],
                    'url': cfg.get('url', '') if cfg['mode'] == 'remote' else '',
                    'has_token': bool(cfg.get('token'))}
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return {'configured': False, 'mode': 'local', 'url': '', 'has_token': False}


def configure_connection(*, mode: str, url: str = '', token: str = '') -> dict:
    """Native-only user-selected ACE backend, persisted with private permissions."""
    if mode not in ('local', 'remote'):
        raise ValueError('Invalid ACE-Step connection mode')
    old = connection()
    existing = {}
    try:
        existing = json.loads(_connection_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    if mode == 'remote':
        from .ace_step_http_worker import endpoint_base
        # Reuse trusted endpoint validation without depending on project input.
        parsed = urlsplit(url)
        if parsed.hostname in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('Select local mode for a loopback ACE-Step server')
        if not token and old.get('mode') == 'remote' and old.get('url') == url:
            token = existing.get('token', '')
        if not token or '\n' in token or '\r' in token or len(token) > 4096:
            raise ValueError('An API token is required for remote ACE-Step')
        # Validate against the worker's HTTPS/allowlist rules.
        previous = {key: os.environ.get(key) for key in ('MTA_ACE_STEP_URL', 'MTA_ACE_STEP_TRUSTED_HOST', 'MTA_ACE_STEP_TOKEN')}
        try:
            os.environ.update({'MTA_ACE_STEP_URL': url, 'MTA_ACE_STEP_TRUSTED_HOST': parsed.hostname or '', 'MTA_ACE_STEP_TOKEN': token})
            endpoint_base()
        finally:
            for key, value in previous.items():
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value
    if mode == 'remote':
        stop_server(disable_auto_start=True)
    destination = _connection_file()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    candidate = destination.with_name(destination.name + '.tmp')
    try:
        with candidate.open('w', encoding='utf-8') as stream:
            json.dump({'mode': mode, 'url': url if mode == 'remote' else '',
                       'token': token if mode == 'remote' else ''}, stream)
        os.chmod(candidate, 0o600)
        os.replace(candidate, destination)
    finally:
        candidate.unlink(missing_ok=True)
    apply_connection()
    return connection()


def apply_connection() -> None:
    cfg = connection()
    if cfg['mode'] != 'remote':
        os.environ['MTA_ACE_STEP_URL'] = 'http://127.0.0.1:8001'
        os.environ.pop('MTA_AI_WORKER_ENABLED', None)
        for name in ('MTA_ACE_STEP_TRUSTED_HOST', 'MTA_ACE_STEP_TOKEN'):
            os.environ.pop(name, None)
        return
    raw = json.loads(_connection_file().read_text(encoding='utf-8'))
    os.environ['MTA_AI_WORKER_ENABLED'] = 'true'
    os.environ['MTA_AI_WORKER_EXECUTABLE'] = str(Path(__file__).with_name('ace_step_http_worker.py').resolve())
    os.environ['MTA_ACE_STEP_URL'] = raw['url']
    os.environ['MTA_ACE_STEP_TRUSTED_HOST'] = urlsplit(raw['url']).hostname or ''
    os.environ['MTA_ACE_STEP_TOKEN'] = raw['token']


def _cache_size(root: Path) -> int:
    """Approximate persistent cache size; never report a fabricated download percent."""
    total = 0
    if root.is_dir():
        for base, _dirs, names in os.walk(root):
            for name in names:
                try:
                    total += (Path(base)/name).stat().st_size
                except OSError:
                    continue
    return total


def _update_progress(phase: str, percent: int | None, message: str = '') -> None:
    with _LOCK:
        _TASK.update({'state': 'installing', 'phase': phase,
                      'progress_percent': percent, 'message': message[-240:]})


def _run_with_progress(command: list[str], *, cwd: Path | None, timeout: int, phase: str) -> None:
    """Read command output while running; do not buffer the entire install in RAM."""
    _update_progress(phase, 0 if phase == 'clone' else None)
    proc = subprocess.Popen(command, cwd=cwd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, text=True, errors='replace', bufsize=1)
    if proc.stderr is None:
        proc.kill()
        proc.wait()
        raise RuntimeError("Could not capture ACE-Step installation progress")
    deadline = time.monotonic() + timeout
    # Git uses CR progress lines; reading one character at a time handles both CR and LF.
    line = ''
    try:
        while True:
            if time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(command, timeout)
            char = proc.stderr.read(1)
            if not char:
                break
            if char in '\r\n':
                if line:
                    if phase == 'clone':
                        match = re.search(r'(?:Receiving objects|Resolving deltas|Updating files):\s*(\d+)%', line)
                        pct = int(match.group(1)) if match else None
                        if pct is not None:
                            _update_progress(phase, pct, line)
                    else:
                        _update_progress(phase, None, line)
                line = ''
            elif len(line) < 2000:
                line += char
        if proc.wait(timeout=5) != 0:
            raise RuntimeError(f'{phase} failed with exit code {proc.returncode}: {line[-200:]}')
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stderr.close()


def _perform_install() -> None:
    global _TASK
    root = home(); folder=root/'source'
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if folder.exists() and not (folder/'.git').is_dir():
            raise RuntimeError('Installation directory exists but is not a Git checkout')
        if not folder.exists():
            _run_with_progress(['git','clone','--progress','--depth','1',SOURCE,str(folder)],cwd=None,timeout=600,phase='clone')
        # uv output does not provide a reliable overall percentage.
        _run_with_progress(['uv','sync','--frozen'],cwd=folder,timeout=1800,phase='dependencies')
        with _LOCK: _TASK={'state':'installed','phase':'complete','progress_percent':100}
    except (OSError,RuntimeError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        with _LOCK: _TASK={'state':'failed','error':str(exc)[:300], 'phase':_TASK.get('phase')}


def install(*, confirmed: bool) -> dict:
    global _TASK
    if not confirmed: raise ValueError('Explicit installation consent is required')
    if not shutil.which('uv') or not shutil.which('git'):
        raise RuntimeError('Git and uv must be installed before automatic ACE-Step setup')
    with _LOCK:
        if _TASK.get('state')=='installing': return status()
        _TASK={'state':'installing','id':uuid.uuid4().hex}
    threading.Thread(target=_perform_install,daemon=True,name='mta-ace-install').start()
    return status()


def _consent_file() -> Path:
    return home() / 'local-server-consent.json'


def _remember_consent() -> None:
    """Persist explicit permission for future starts (models may download on demand)."""
    root = home()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    dst = _consent_file()
    tmp = dst.with_name(dst.name + '.tmp')
    try:
        with tmp.open('w', encoding='utf-8') as stream:
            json.dump({'auto_start': True, 'model_download_consent': True}, stream)
        os.chmod(tmp, 0o600)
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)


def _previous_consent() -> bool:
    try:
        data = json.loads(_consent_file().read_text(encoding='utf-8'))
        return data.get('auto_start') is True and data.get('model_download_consent') is True
    except (OSError, ValueError, TypeError):
        return False


def auto_start_server() -> dict:
    """Start only after prior explicit consent; never install/download silently."""
    apply_connection()
    if connection()['mode'] == 'remote' or not _previous_consent():
        return status()
    try:
        return start_server(confirmed_model_download=True, remember_consent=False)
    except (OSError, RuntimeError) as exc:
        with _LOCK:
            _TASK.update({'startup_error': str(exc)[:300]})
        return status()


def stop_server(*, disable_auto_start: bool = False) -> dict:
    """Stop only the process spawned by MTA; leave unrelated servers alone."""
    global _PROCESS
    with _LOCK:
        proc = _PROCESS
        _PROCESS = None
    if proc is not None and proc.poll() is None:
        try:
            if os.name == 'posix':
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                if os.name == 'posix':
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
                proc.wait(timeout=5)
        except (OSError, ProcessLookupError):
            pass
    if disable_auto_start:
        _consent_file().unlink(missing_ok=True)
    return status()


def start_server(*, confirmed_model_download: bool, remember_consent: bool = True) -> dict:
    global _PROCESS, _CACHE_BASELINE
    if connection()['mode'] == 'remote': raise RuntimeError('Switch to local ACE-Step mode before starting a local server')
    if not confirmed_model_download: raise ValueError('Model download consent required')
    folder=home()/'source'
    if not (folder/'.venv').is_dir(): raise RuntimeError('Install ACE-Step first')
    with _LOCK:
        if _PROCESS is not None and _PROCESS.poll() is None: return status()
        cache=home()/'models';cache.mkdir(parents=True,exist_ok=True,mode=0o700)
        _CACHE_BASELINE = _cache_size(cache)
        _TASK.update({'state':'starting_server','phase':'model_initialization','progress_percent':None})
        env={**os.environ,'HF_HOME':str(cache),'HOST':'127.0.0.1','PORT':'8001','CHECK_UPDATE':'false'}
        log_path=home()/'server.log'
        options = {'start_new_session': True} if os.name == 'posix' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
        with log_path.open('ab') as log:
            _PROCESS=subprocess.Popen(['uv','run','--no-sync','acestep-api'],cwd=folder,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,**options)
        if remember_consent:
            _remember_consent()
        # Register the built-in, trusted adapter in the native MTA process.
        os.environ['MTA_AI_WORKER_ENABLED']='true'
        os.environ['MTA_AI_WORKER_EXECUTABLE']=str(Path(__file__).with_name('ace_step_http_worker.py').resolve())
        os.environ['MTA_ACE_STEP_URL']='http://127.0.0.1:8001'
    return status()
