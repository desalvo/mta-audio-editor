"""Native ACE-Step setup after explicit Local selection.

Use packaged uv and an official pinned source archive, without shell bootstrap
commands. Model downloads and future automatic starts follow saved consent.
"""
from __future__ import annotations
from .service_admission import worker_thread
import os
import json
import signal
from pathlib import Path
from urllib.parse import urlsplit
import shutil
import subprocess
import threading
import uuid
import time
import sys
from urllib.request import Request, build_opener, ProxyHandler

SOURCE_ARCHIVE = 'https://codeload.github.com/ACE-Step/ACE-Step-1.5/zip/refs/tags/v0.1.8'
_LOCK = threading.RLock()
_TASK: dict = {'state': 'idle'}
_PROCESS: subprocess.Popen | None = None
_CACHE_BASELINE = 0
_SETUP_ACTIVE = False
_READY = False
_SETUP_EPOCH = 0
_INSTALL_PROCESS = None



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
    return {'server_ready':bool(running and _READY), 'task':task,'auto_start_enabled':_consent_file().is_file(),'installed':(folder/'pyproject.toml').is_file() and (folder/'.venv').is_dir() and (not (folder/'.mta-managed-archive').exists() or (folder/'.mta-install-complete').is_file()),
            'server_running':running,'has_git':bool(shutil.which('git')),'has_uv':bool(_tool('uv')),
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
                    'has_token': bool(cfg.get('token')) or cfg.get('transport')=='mta-account',
                    'transport':cfg.get('transport','ace-direct')}
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
        # Preserve a running local adapter; selection must not disable it.
        if _PROCESS is not None and _PROCESS.poll() is None:
            _activate_adapter()
        for name in ('MTA_ACE_STEP_TRUSTED_HOST', 'MTA_ACE_STEP_TOKEN'):
            os.environ.pop(name, None)
        return
    raw = json.loads(_connection_file().read_text(encoding='utf-8'))
    if raw.get('transport') == 'mta-account':
        return  # MTA account requests use the metered API, never raw ACE proxy.
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
    """Stream bounded progress, with a watchdog even when the child is silent."""
    global _INSTALL_PROCESS
    import queue
    epoch=_SETUP_EPOCH
    _update_progress(phase, None)
    proc=subprocess.Popen(command,cwd=cwd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
      text=True,errors='replace',bufsize=1,**({'start_new_session':True} if os.name=='posix' else {'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP}))
    _INSTALL_PROCESS=proc
    lines=queue.Queue(maxsize=128);closed=threading.Event()
    def read():
        line=''
        try:
            while not closed.is_set():
                char=proc.stderr.read(1)
                if not char:break
                if char in '\r\n':
                    if line:
                        while not closed.is_set():
                            try:lines.put(line,timeout=.2);break
                            except queue.Full:continue
                    line=''
                elif len(line)<2000:line+=char
        except (OSError,ValueError):
            closed.set()
    reader=worker_thread(target=read,daemon=True,name='mta-ace-install-progress');reader.start()
    deadline=time.monotonic()+timeout
    try:
        while proc.poll() is None or not lines.empty():
            if time.monotonic()>deadline:raise subprocess.TimeoutExpired(command,timeout)
            try:line=lines.get(timeout=.2)
            except queue.Empty:continue
            if epoch==_SETUP_EPOCH:_update_progress(phase,None,line)
        if proc.wait(timeout=5)!=0:raise RuntimeError('ACE_INSTALL_DEPENDENCIES_FAILED')
    finally:
        closed.set()
        if _INSTALL_PROCESS is proc:_INSTALL_PROCESS=None
        if os.name=='posix':
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        if proc.poll() is None:proc.kill();proc.wait()
        reader.join(2)
        if proc.stderr is not None:proc.stderr.close()


def _perform_install() -> None:
    global _TASK
    epoch=_SETUP_EPOCH
    root = home(); folder=root/'source'
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if folder.exists() and not ((folder/'.git').is_dir() or (folder/'.mta-managed-archive').is_file()):
            raise RuntimeError('Installation directory exists but is not a Git checkout')
        if not folder.exists():
            _download_source(folder)
        # uv output does not provide a reliable overall percentage.
        _run_with_progress([_tool('uv'),'sync','--frozen'],cwd=folder,timeout=1800,phase='dependencies')
        (folder/'.mta-install-complete').write_text('ACE-Step dependencies ready\n')
        with _LOCK:
            if epoch==_SETUP_EPOCH:_TASK={'state':'installed','phase':'complete','progress_percent':100}
    except (OSError,RuntimeError,ValueError,subprocess.CalledProcessError,subprocess.TimeoutExpired, __import__('zipfile').BadZipFile) as exc:
        with _LOCK:
            if epoch==_SETUP_EPOCH:_TASK={'state':'failed','error':str(exc)[:300], 'phase':_TASK.get('phase')}


def install(*, confirmed: bool) -> dict:
    global _TASK
    if not confirmed: raise ValueError('Explicit installation consent is required')
    if not _tool('uv'):
        raise RuntimeError('ACE_UV_MISSING')
    with _LOCK:
        if _TASK.get('state')=='installing' or _SETUP_ACTIVE: return status()
        _TASK={'state':'installing','id':uuid.uuid4().hex}
    worker_thread(target=_perform_install,daemon=True,name='mta-ace-install').start()
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
        return ensure_local(confirmed=True)
    except (OSError, RuntimeError) as exc:
        with _LOCK:
            _TASK.update({'startup_error': str(exc)[:300]})
        return status()


def stop_server(*, disable_auto_start: bool = False) -> dict:
    """Stop only the process spawned by MTA; leave unrelated servers alone."""
    global _PROCESS, _READY, _SETUP_EPOCH
    with _LOCK:
        _SETUP_EPOCH += 1
        _READY = False
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
    install_proc=_INSTALL_PROCESS
    if install_proc is not None and install_proc.poll() is None:
        try:
            if os.name=='posix':os.killpg(install_proc.pid,signal.SIGTERM)
            else:install_proc.terminate()
        except OSError:
            pass
    with _LOCK:
        if _TASK.get('state') in ('installing','starting_server','ready'):_TASK.update(state='stopped',phase='stopped',progress_percent=None)
    if disable_auto_start:
        _consent_file().unlink(missing_ok=True)
    return status()


def start_server(*, confirmed_model_download: bool, remember_consent: bool = True) -> dict:
    global _PROCESS, _CACHE_BASELINE, _READY
    if connection()['mode'] == 'remote': raise RuntimeError('Switch to local ACE-Step mode before starting a local server')
    if not confirmed_model_download: raise ValueError('Model download consent required')
    folder=home()/'source'
    if not (folder/'.venv').is_dir(): raise RuntimeError('Install ACE-Step first')
    with _LOCK:
        if _PROCESS is not None and _PROCESS.poll() is None: return status()
        cache=home()/'models';cache.mkdir(parents=True,exist_ok=True,mode=0o700)
        _CACHE_BASELINE = _cache_size(cache)
        _READY = False
        _TASK.update({'state':'starting_server','phase':'model_initialization','progress_percent':None})
        env={**os.environ,'HF_HOME':str(cache),'HOST':'127.0.0.1','PORT':'8001','CHECK_UPDATE':'false'}
        log_path=home()/'server.log'
        options = {'start_new_session': True} if os.name == 'posix' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
        _activate_adapter()
        with log_path.open('ab') as log:
            python=folder/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            if not python.is_file():raise RuntimeError('ACE_PYTHON_MISSING')
            _PROCESS=subprocess.Popen([str(python),'-m','acestep.api_server','--host','127.0.0.1','--port','8001','--no-init'],cwd=folder,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,**options)
        if remember_consent:
            _remember_consent()
        # The trusted adapter was registered before the server was spawned.
        os.environ['MTA_ACE_STEP_URL']='http://127.0.0.1:8001'
    return status()


_ADAPTER_FILES = ('ace_step_http_worker.py', 'ace_gpu_process_meter.py', 'ai_gpu_process_meter.py',
    'ai_proxmox_gpu_agent_client.py', 'ace_gpu_profiler.py', 'ai_gpu_verified.py', 'ace_task_progress.py', 'ai_execution_limits.py')


def adapter_python(worker):
    if Path(worker).resolve() == (home()/'adapter'/'ace_step_http_worker.py').resolve():
        python = home()/'source'/'.venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if python.is_file() and not python.is_symlink():
            return python
        # uv normally creates a venv Python symlink to its managed interpreter.
        if python.is_file():
            return python
    return None


def _activate_adapter():
    directory = home()/'adapter'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in _ADAPTER_FILES:
        source = Path(__file__).with_name(name)
        destination = directory/name
        # Sources shipped with MTA; never obtained from a project or request.
        with source.open('rb') as src, destination.open('wb') as dst:
            shutil.copyfileobj(src, dst)
        destination.chmod(0o700 if name == 'ace_step_http_worker.py' else 0o600)
    os.environ['MTA_AI_WORKER_ENABLED'] = 'true'
    os.environ['MTA_AI_WORKER_EXECUTABLE'] = str(directory/'ace_step_http_worker.py')


def _health_ready():
    # Loopback only, no proxy or redirect; process existence is not readiness.
    from urllib.request import HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(Request('http://127.0.0.1:8001/health'), timeout=2) as response:
            data = json.loads(response.read(16384))
            return response.status == 200 and isinstance(data, dict) and data.get('status') not in ('error','failed')
    except (OSError, ValueError):
        return False


def ensure_local(*, confirmed: bool):
    """Choosing Local authorizes setup and weights download; only one setup runs."""
    global _SETUP_ACTIVE, _SETUP_EPOCH, _TASK
    if not confirmed:
        raise ValueError('Local setup consent required')
    if connection()['mode'] == 'remote':
        raise RuntimeError('Select local mode first')
    _remember_consent()
    with _LOCK:
        if _SETUP_ACTIVE:
            return status()
        _SETUP_ACTIVE = True
        _SETUP_EPOCH += 1
        epoch = _SETUP_EPOCH
        _TASK = {'state':'installing', 'phase':'checking_prerequisites', 'progress_percent':None}
    def setup():
        global _SETUP_ACTIVE, _TASK, _READY
        try:
            installed = status()['installed']
            if not installed:
                if not _tool('uv'):
                    raise RuntimeError('ACE_PREREQUISITES_MISSING')
                _perform_install()
                if _TASK.get('state') == 'failed':
                    return
            with _LOCK:
                if epoch != _SETUP_EPOCH or connection()['mode'] != 'local':
                    return
                start_server(confirmed_model_download=True)
            deadline = time.monotonic()+1800
            while time.monotonic() < deadline:
                with _LOCK:
                    if epoch != _SETUP_EPOCH or connection()['mode'] != 'local':
                        return
                    if _PROCESS is None or _PROCESS.poll() is not None:
                        raise RuntimeError('ACE_SERVER_EXITED')
                if _health_ready():
                    with _LOCK:
                        if epoch == _SETUP_EPOCH:
                            _READY = True
                            _TASK = {'state':'ready','phase':'ready','progress_percent':100}
                    return
                time.sleep(1)
            raise RuntimeError('ACE_STARTUP_TIMEOUT')
        except (OSError, ValueError, RuntimeError) as exc:
            with _LOCK:
                if epoch == _SETUP_EPOCH:
                    _READY = False
                    _TASK = {'state':'failed','phase':'setup','error':str(exc)[:300]}
        finally:
            with _LOCK:
                _SETUP_ACTIVE = False
    worker_thread(target=setup, daemon=True, name='mta-ace-local-setup').start()
    return status()


def _tool(name):
    bundled=Path(getattr(sys,'_MEIPASS',Path(__file__).parent.parent))/'tools'/(name+'.exe' if os.name=='nt' else name)
    return str(bundled) if bundled.is_file() else shutil.which(name)


def _download_source(folder):
    """Official pinned source archive; no Git installation or shell bootstrap."""
    import tempfile
    import zipfile
    from urllib.request import HTTPSHandler,HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    root=folder.parent;epoch=_SETUP_EPOCH
    with tempfile.TemporaryDirectory(dir=root,prefix='.ace-source-') as scratch:
        archive=Path(scratch)/'source.zip'
        request=Request(SOURCE_ARCHIVE)  # noqa: S310 -- fixed official HTTPS archive
        with build_opener(HTTPSHandler(),NoRedirect()).open(request,timeout=60) as response,archive.open('wb') as stream:
            total=int(response.headers.get('Content-Length','0'));received=0;started=time.monotonic()
            while True:
                chunk=response.read(256*1024)
                if not chunk:break
                if epoch!=_SETUP_EPOCH:raise RuntimeError('ACE_SETUP_CANCELLED')
                received+=len(chunk)
                if received>128*1024*1024 or time.monotonic()-started>600:raise RuntimeError('ACE_SOURCE_DOWNLOAD_LIMIT')
                stream.write(chunk)
                _update_progress('clone',min(99,int(received*100/total)) if total else None,
                  str(received//1048576)+' MiB')
        extraction=Path(scratch)/'unpacked'
        with zipfile.ZipFile(archive) as z:
            infos=z.infolist()
            if len(infos)>20000 or sum(i.file_size for i in infos)>512*1024*1024:raise RuntimeError('ACE_SOURCE_ARCHIVE_LIMIT')
            for info in infos:
                dest=extraction/info.filename
                if not dest.resolve().is_relative_to(extraction.resolve()) or (info.external_attr>>16)&0o170000==0o120000:
                    raise RuntimeError('ACE_SOURCE_ARCHIVE_UNSAFE')
            from .chord_ml import _safe_extract
            _safe_extract(z,extraction)
        roots=list(extraction.iterdir())
        if len(roots)!=1 or not (roots[0]/'pyproject.toml').is_file() or not (roots[0]/'uv.lock').is_file():
            raise RuntimeError('ACE_SOURCE_ARCHIVE_INVALID')
        (roots[0]/'.mta-managed-archive').write_text('ACE-Step v0.1.8\n')
        roots[0].replace(folder)


def configure_mta_remote():
    from .native_ai_account import credentials
    cfg=credentials()
    stop_server(disable_auto_start=True)
    destination=_connection_file();destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    import tempfile
    fd,name=tempfile.mkstemp(dir=destination.parent,prefix='.ace-connection-')
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as stream:json.dump({'mode':'remote','transport':'mta-account','url':cfg['url']},stream)
        os.replace(name,destination)
    finally:
        if os.path.exists(name):os.unlink(name)
    return connection()


def uses_mta_account():
    try:return json.loads(_connection_file().read_text()).get('transport')=='mta-account' and connection()['mode']=='remote'
    except (OSError,ValueError):return False
