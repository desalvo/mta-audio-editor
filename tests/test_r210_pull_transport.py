"""Independent Linux worker processes and private verified HTTPS authority."""
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app import ai_pull_coordinator as central, ai_pull_worker as worker, auth
from test_r208_unified_adapter_billing_e2e import operator as operator  # noqa: F401
from test_r210_pull_coordinator import authority as authority, enqueue, economic  # noqa: F401
from test_r210_pull_lifecycle import api as api  # noqa: F401


@pytest.fixture
def https(authority, api, tmp_path):
    cert, key = tmp_path / 'authority.pem', tmp_path / 'authority.key'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                    '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1',
                    '-keyout', str(key), '-out', str(cert)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    state = {'requests': [], 'drops': {}, 'redirect': False}
    client = api[0]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            state['requests'].append(self.path)
            if state['redirect']:
                self.send_response(302)
                self.send_header('Location', 'https://127.0.0.1:1/untrusted')
                self.end_headers()
                return
            data = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            response = client.post(self.path, content=data, headers={'Authorization': self.headers.get('Authorization',''),
                                                                     'Content-Type': 'application/json'})
            action = self.path.rsplit('/', 1)[-1]
            if state['drops'].get(action, 0):
                state['drops'][action] -= 1
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            self.send_response(response.status_code)
            self.send_header('Content-Length', str(len(response.content)))
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(response.content)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.update(url='https://127.0.0.1:' + str(server.server_port), ca_file=str(cert))
    try:
        yield state
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()


def cli(authority, https, name, *, credential=None):
    folder = authority[2] / name
    folder.mkdir(mode=0o700, exist_ok=True)
    config = folder / 'worker.json'
    config.write_text(json.dumps({'url': https['url'], 'credential': credential or authority[1]['credential'], 'ca_file': https['ca_file']}))
    config.chmod(0o600)
    env = {**os.environ, 'MTA_DATA_DIR': str(folder / 'worker-private-config'),
           'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
    # Explicit dependency injection in this generated protocol test process.
    # Synthetic WAV writers have no checkpoint and are not production plugins.
    bootstrap = ('from pathlib import Path; import runpy; from app import ai_adapter_identity as identity; '
                 'original=identity.supported_worker; root=Path(' + repr(str(authority[2])) + '); '
                 'identity.supported_worker=lambda kind,path: '
                 '(Path(path).is_file() and Path(path).resolve().is_relative_to(root.resolve())) or original(kind,path); '
                 'runpy.run_module("app.ai_pull_worker",run_name="__main__")')
    args = [sys.executable, '-c', bootstrap, '--config', str(config), '--state', str(folder / 'state')]
    return args, env, folder


def run_cli(configuration):
    args, env, _ = configuration
    return subprocess.run(args, env=env, capture_output=True, timeout=20)


def test_two_separate_worker_processes_share_only_https_not_sqlite(authority, https):
    job = enqueue(authority)
    other = central.register('independent-second-host', ['whisper'])
    first, second = cli(authority, https, 'node-one'), cli(authority, https, 'node-two', credential=other['credential'])
    processes = [subprocess.Popen(c[0], env=c[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for c in (first, second)]
    try:
        for proc in processes:
            out, err = proc.communicate(timeout=20)
            assert proc.returncode == 0, (out, err)
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
    assert economic(job) == ('done','finished','closed')
    assert sum(path.endswith('/complete') for path in https['requests']) == 1
    assert (authority[2] / 'execution-count').read_bytes() == b'1'
    for config in (first, second):
        assert not list(config[2].rglob('*.sqlite*'))
        phase = json.loads((config[2] / 'state/active.json').read_text())['phase']
        assert phase in ('done','idle')


@pytest.mark.parametrize('lost', ['claim','complete'])
def test_partition_after_committed_claim_or_completion_never_reexecutes(authority, https, lost):
    job = enqueue(authority)
    https['drops'][lost] = 1
    configuration = cli(authority, https, 'response-lost')
    first = run_cli(configuration)
    assert first.returncode == 1, first.stderr
    state = json.loads((configuration[2] / 'state/active.json').read_text())
    assert state['phase'] == ('requesting' if lost == 'claim' else 'ready')
    assert economic(job) == (('running','running','open') if lost == 'claim' else ('done','finished','closed'))
    second = run_cli(configuration)
    assert second.returncode == 0, second.stderr
    assert economic(job) == ('done','finished','closed')
    assert sum(path.endswith('/complete') for path in https['requests']) == (1 if lost == 'claim' else 2)
    assert (authority[2] / 'execution-count').read_bytes() == b'1'


def test_untrusted_tls_never_transmits_worker_credential(authority, https):
    client = worker.WorkerClient(https['url'], authority[1]['credential'])
    with pytest.raises(ssl.SSLCertVerificationError):
        client.call('claim', {'instance': 'a' * 32})
    assert https['requests'] == []


def test_redirect_cannot_forward_credential(authority, https):
    https['redirect'] = True
    client = worker.WorkerClient(https['url'], authority[1]['credential'], ca_file=https['ca_file'])
    with pytest.raises(worker.WorkerHTTP) as error:
        client.call('claim', {'instance': 'a' * 32})
    assert error.value.status == 302 and https['requests'] == ['/api/pull-worker/claim']


@pytest.mark.parametrize('change', ['credential','trust'])
def test_journal_rejects_authority_key_and_trust_drift_before_network(authority, https, change, monkeypatch):
    client = worker.WorkerClient(https['url'], authority[1]['credential'], ca_file=https['ca_file'])
    state_dir = authority[2] / 'bound-state'
    assert not worker.run_once(client, state_dir)
    old_count = len(https['requests'])
    if change == 'credential':
        other = central.register('different-node', ['whisper'])
        other_client = worker.WorkerClient(https['url'], other['credential'], ca_file=https['ca_file'])
    else:
        other_client = worker.WorkerClient(https['url'], authority[1]['credential'])
    with pytest.raises(worker.WorkerUncertain):
        worker.run_once(other_client, state_dir)
    assert len(https['requests']) == old_count


def test_dispatched_journal_never_reexecutes_after_actual_supervisor_sigkill(authority, https, monkeypatch):
    job = enqueue(authority)
    pidfile = authority[2] / 'actual-child.pid'
    script = authority[2] / 'sleeping-worker.py'
    script.write_text('''import os,time
from pathlib import Path
Path(''' + repr(str(pidfile)) + ''').write_text(str(os.getpid()))
time.sleep(30)
''')
    script.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_EXECUTABLE', str(script))
    config = cli(authority, https, 'killed-worker')
    proc = subprocess.Popen(config[0], env=config[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    child = None
    try:
        deadline = time.monotonic() + 10
        while not pidfile.exists() and proc.poll() is None and time.monotonic() < deadline:
            threading.Event().wait(.02)
        assert pidfile.exists()
        child = int(pidfile.read_text())
        proc.kill()
        proc.wait(timeout=5)
        assert json.loads((config[2] / 'state/active.json').read_text())['phase'] == 'dispatched'
        again = run_cli(config)
        assert again.returncode == 78
        assert economic(job) == ('running','running','open')
        with auth.db() as c:
            with pytest.raises(central.PullPending):
                central.erasure_safe(c, authority[0])
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        if child is None and pidfile.exists():
            child = int(pidfile.read_text())
        if child is not None:
            try:
                os.kill(child, 9)
            except ProcessLookupError:
                pass


def test_shared_worker_state_lock_serializes_two_processes(authority, https):
    job = enqueue(authority)
    config = cli(authority, https, 'shared-state')
    processes = [subprocess.Popen(config[0], env=config[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
    try:
        for proc in processes:
            out, err = proc.communicate(timeout=20)
            assert proc.returncode == 0, (out, err)
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
    assert economic(job) == ('done','finished','closed')
    assert sum(path.endswith('/complete') for path in https['requests']) == 1


def test_actual_authority_sigkill_after_frozen_result_recovers_without_new_inference(authority, https):
    """Real FastAPI/HTTPS process dies after freeze and before ledger settlement."""
    from app import ai_request_dedup as dedup, ai_access
    from test_r208_unified_adapter_billing_e2e import source_audio
    request_key = 'authority-crash-original-request'
    digest = dedup.fingerprint('whisper', b'{}', source_audio())
    dedup.admit(authority[0], request_key, digest)
    job = central.enqueue(authority[0], 'whisper', {}, source_wav=source_audio(), request_key=request_key, request_digest=digest)
    ai_token = ai_access.issue(authority[0], 'crash recovery client')['token']
    marker = authority[2] / 'authority-crashed'
    bootstrap = authority[2] / 'authority.py'
    bootstrap.write_text('''import os,signal,sys
from pathlib import Path
from app import main,ai_billing
import uvicorn
original=ai_billing.finish_job_idempotent
def crash(*a,**kw):
 marker=Path(sys.argv[4])
 if not marker.exists():
  marker.touch();os.kill(os.getpid(),signal.SIGKILL)
 return original(*a,**kw)
ai_billing.finish_job_idempotent=crash
uvicorn.run(main.app,host='127.0.0.1',port=int(sys.argv[1]),ssl_certfile=sys.argv[2],ssl_keyfile=sys.argv[3],lifespan='off',log_level='critical')
''')
    with socket.socket() as reserve:
        reserve.bind(('127.0.0.1', 0))
        port = reserve.getsockname()[1]
    cert = Path(https['ca_file'])
    key = cert.with_name('authority.key')
    env = {**os.environ, 'MTA_DATA_DIR': str(auth.data_root()),
           'MTA_AI_JOB_STATE_DIR': str(authority[2] / 'server-queue'),
           'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
    command = [sys.executable, str(bootstrap), str(port), str(cert), str(key), str(marker)]
    def start():
        process = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 10
        context = ssl.create_default_context(cafile=str(cert))
        while time.monotonic() < deadline and process.poll() is None:
            try:
                with context.wrap_socket(socket.socket(), server_hostname='localhost') as probe:
                    probe.settimeout(.3)
                    probe.connect(('127.0.0.1', port))
                return process
            except OSError:
                threading.Event().wait(.03)
        if process.poll() is None:
            process.kill()
        _, stderr = process.communicate(timeout=5)
        pytest.fail('Isolated authority did not start: ' + stderr.decode()[-1000:])
    endpoint = {**https, 'url': 'https://127.0.0.1:' + str(port)}
    config = cli(authority, endpoint, 'authority-crash-worker')
    process = start()
    try:
        first = run_cli(config)
        assert first.returncode == 1, first.stderr
        process.wait(timeout=5)
        assert marker.exists() and process.returncode != 0
        assert economic(job) == ('running','running','open')
        assert json.loads((config[2] / 'state/active.json').read_text())['phase'] == 'ready'
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    process = start()
    try:
        second = run_cli(config)
        assert second.returncode == 0, second.stderr
        assert economic(job) == ('done','finished','closed')
        assert (authority[2] / 'execution-count').read_bytes() == b'1'
        import http.client
        connection = http.client.HTTPSConnection('127.0.0.1', port, context=ssl.create_default_context(cafile=str(cert)), timeout=5)
        try:
            connection.request('GET', '/api/ai-jobs/request-result/' + request_key,
                               headers={'Authorization': 'Bearer ' + ai_token})
            response = connection.getresponse()
            assert response.status == 200 and response.read() == source_audio()
            assert response.getheader('X-MTA-AI-Job-ID') == job
        finally:
            connection.close()
    finally:
        process.kill()
        process.wait(timeout=5)
