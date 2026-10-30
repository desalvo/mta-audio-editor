"""Operator-owned Linux pull worker with a durable no-reexecution barrier.

python -m app.ai_pull_worker --config /private/worker.json --state /private/state
Use --watch for the optional service. Exit 78 requires operator review.
"""
import argparse
import base64
import hashlib
import http.client
import os
from pathlib import Path
import secrets
import ssl
import stat
import sys
import tempfile
import time
from urllib.parse import urlsplit

from . import ai_pull_coordinator as protocol
from . import platform_file_lock as locks


class WorkerUncertain(RuntimeError):
    pass


class WorkerHTTP(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__('Worker authority returned HTTP ' + str(status))


def private_file(path, *, limit=48 * 1024 * 1024):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > limit):
            raise ValueError('Private owner-only regular file required')
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Private file exceeds limit')
        return data


class WorkerClient:
    def __init__(self, url, credential, *, ca_file=None):
        parts = urlsplit(url)
        if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
                or parts.query or parts.fragment or parts.path not in ('', '/')
                or any(ord(ch) <= 32 or ord(ch) >= 127 for ch in url) or '%' in url or '\\' in url
                or not isinstance(credential, str) or protocol.re.fullmatch(r'[a-f0-9]{32}\.[a-f0-9]{64}', credential) is None):
            raise ValueError('Fixed private HTTPS authority and worker credential required')
        if parts.port == 0:
            raise ValueError('Invalid authority port')
        self.host, self.port, self.credential = parts.hostname, parts.port or 443, credential
        self.context = ssl.create_default_context(cafile=ca_file)
        roots = sorted(hashlib.sha256(b).hexdigest() for b in self.context.get_ca_certs(binary_form=True))
        profile = {'host': self.host, 'port': self.port, 'credential_sha256': hashlib.sha256(credential.encode()).hexdigest(),
                   'trust_roots': roots, 'explicit_ca_sha256': hashlib.sha256(Path(ca_file).read_bytes()).hexdigest() if ca_file else None}
        self.binding = hashlib.sha256(protocol.encode(profile).encode()).hexdigest()

    def call(self, action, body, *, job=None):
        if action not in ('claim', 'heartbeat', 'complete') or (action != 'claim' and
                (not isinstance(job, str) or not protocol.HEX.fullmatch(job))):
            raise ValueError('Invalid worker control path')
        path = '/api/pull-worker/claim' if action == 'claim' else '/api/pull-worker/' + job + '/' + action
        conn = http.client.HTTPSConnection(self.host, self.port, context=self.context, timeout=30)
        try:
            conn.request('POST', path, protocol.encode(body).encode(), headers={
                'Authorization': 'Bearer ' + self.credential, 'Content-Type': 'application/json', 'Accept': 'application/json'})
            response = conn.getresponse()
            if response.status != 200:
                raise WorkerHTTP(response.status)
            data = response.read(24 * 1024 * 1024 + 1)
            if len(data) > 24 * 1024 * 1024:
                raise ValueError('Oversized worker response')
            return protocol.decode(data)
        finally:
            conn.close()


def _write(path, value):
    fd, name = tempfile.mkstemp(prefix='.pull-journal-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(protocol.encode(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)
    finally:
        Path(name).unlink(missing_ok=True)


def _task(value, instance):
    if not isinstance(value, dict) or value.get('instance') != instance:
        raise ValueError('Invalid worker assignment')
    if not protocol.HEX.fullmatch(value.get('job_id', '')) or protocol.re.fullmatch(r'[a-f0-9]{64}', value.get('nonce', '')) is None:
        raise ValueError('Invalid worker receipt')
    if value.get('cancelled') is True:
        return b''
    if set(value)-{'model_requirement'} != {'job_id','kind','instance','nonce','source_kind','source_sha256','timeout','plan','policy','source_b64'}:
        raise ValueError('Invalid assignment fields')
    if 'model_requirement' in value and not isinstance(value['model_requirement'],dict):
        raise ValueError('Invalid model requirement')
    from .ai_worker_registry import registered_kinds
    from .ai_remote_transport import validate_audio_options
    if value['kind'] not in registered_kinds() or type(value['timeout']) is not int or not 1 <= value['timeout'] <= 86400:
        raise ValueError('Invalid assignment engine/timeout')
    validate_audio_options(value['plan'])
    if value['plan'].get('kind', value['kind']) != value['kind']:
        raise ValueError('Assignment cannot override engine')
    raw = value['source_b64']
    if not isinstance(raw, str) or len(raw) > 4 * protocol.MAX_BYTES // 3 + 8:
        raise ValueError('Oversized worker source')
    source = base64.b64decode(raw, validate=True)
    if len(source) > protocol.MAX_BYTES or hashlib.sha256(source).hexdigest() != value['source_sha256']:
        raise ValueError('Worker source integrity failed')
    return source


def _run(client, journal, state):
    task = state['task']
    source = _task(task, state['instance'])
    outcome = {'status': 'failed', 'cpu_seconds': None, 'media_type': None, 'result_b64': ''}
    if task.get('cancelled'):
        outcome['status'] = 'cancelled'
        return outcome
    from dataclasses import asdict
    from .ai_model_attestation import authorize,verify_contract,VERIFIED_SCHEMA
    from .ai_worker_registry import resolve_worker, worker_python
    from .ai_worker_artifacts import package_artifacts, _verify_wav_bytes
    from .ai_metering_agent import run_supervised_process
    from .ai_execution_policy import KEY
    decision,local_requirement = authorize(task['kind'], task['plan'])
    if asdict(decision) != task['policy']:
        raise ValueError('Worker model policy differs from admitted authority policy')
    worker = resolve_worker(task['kind'])
    if worker is None:
        raise ValueError('Operator-selected engine is unavailable on this worker')
    from .ai_model_attestation import CONTEXT,RECEIPT,context,validate
    model_requirement=task.get('model_requirement')
    if local_requirement and local_requirement.get('schema')==VERIFIED_SCHEMA and (
            model_requirement is None or model_requirement.get('schema')!=VERIFIED_SCHEMA):
        raise ValueError('Original reviewed checkpoint requirement missing; no unattested fallback')
    if model_requirement is not None and model_requirement.get('schema')==VERIFIED_SCHEMA:
        verify_contract(model_requirement,decision)
    if model_requirement is not None:
        if (task['kind']!='audio-to-midi-basic-pitch'
                or model_requirement.get('schema') not in ('mta-basic-pitch-load-1',VERIFIED_SCHEMA)
                or model_requirement.get('policy')!=task['policy']
                or worker!=Path(__file__).with_name('ai_studio_adapter.py')
                or hashlib.sha256(worker.read_bytes()).hexdigest()!=model_requirement.get('adapter_sha256',model_requirement.get('sources',{}).get('ai_studio_adapter.py'))):
            raise ValueError('Unsupported or changed attested adapter')
    cancelled = False
    pulse_at = float('-inf')
    def heartbeat():
        nonlocal cancelled, pulse_at
        if time.monotonic() - pulse_at >= 1:
            pulse_at = time.monotonic()
            result = client.call('heartbeat', {'instance': state['instance'], 'nonce': task['nonce']}, job=task['job_id'])
            if not isinstance(result, dict) or type(result.get('cancelled')) is not bool:
                raise ValueError('Invalid worker heartbeat acknowledgement')
            cancelled = result['cancelled']
        return cancelled
    if heartbeat():
        outcome['status'] = 'cancelled'
        return outcome
    with tempfile.TemporaryDirectory(prefix='execution-', dir=journal.parent) as folder:
        directory = Path(folder)
        plan = {**task['plan'], 'kind': task['kind']}
        if task['source_kind'] == 'wav':
            _verify_wav_bytes(source)
            name = directory / 'source.wav'
            if task['kind'] == 'ace-step':
                (directory / 'inputs').mkdir()
                name = directory / 'inputs/source.wav'
            name.write_bytes(source)
            name.chmod(0o400)
            plan['source_audio'] = [{'filename': 'inputs/source.wav'}] if task['kind'] == 'ace-step' else str(name)
        elif task['source_kind'] == 'score':
            from .studio_score import validate
            if task['kind'] not in ('vocal-harmony', 'vocal-synthesis'):
                raise ValueError('Invalid score assignment')
            validate(source)
            name = directory / 'score.json'
            name.write_bytes(source)
            name.chmod(0o400)
            plan['source_score'] = str(name)
        elif task['source_kind'] != 'none' or source:
            raise ValueError('Invalid source format')
        request = directory / 'request.json'
        request.write_text(protocol.encode(plan))
        request.chmod(0o600)
        command = [worker_python(task['kind']), str(worker)] if worker.suffix == '.py' else [str(worker)]
        command += ['--request', str(request), '--output', str(directory / 'preview.wav')]
        # Durable barrier before Popen. A restarted worker NEVER re-enters here
        # from dispatched, including after uncertain supervisor/partition loss.
        state['phase'] = 'dispatched'
        state['task'] = {k: task[k] for k in ('job_id', 'instance', 'nonce')}
        _write(journal, state)
        measurement = run_supervised_process(command, cwd=folder, timeout_seconds=task['timeout'], cancel_check=heartbeat,
            env={**os.environ,CONTEXT:protocol.encode(context(task)) if model_requirement else '',RECEIPT:str(directory/'model-receipt.json') if model_requirement else '', **{KEY:protocol.encode({'schema':'mta-execution-policy-1','kind':task['kind'],'decision':task['policy']})}, 'MTA_AI_PROGRESS_FILE': str(directory / 'progress.json'),
                 'MTA_AI_JOB_MAX_ARTIFACT_MIB': '16'})
        if not measurement.isolated:
            raise WorkerUncertain('Unverified worker descendants; retain original assignment without settlement')
        outcome['cpu_seconds'] = measurement.usage.get('cpu_seconds') if measurement.isolated else None
        # Freeze known output/CPU before the next network request. The authority
        # atomically handles a concurrent cancellation while freezing completion.
        try:
            model_receipt=None
            if model_requirement is not None:
                model_receipt=protocol.decode(private_file(directory/'model-receipt.json',limit=8192))
                if measurement.pid is None:raise ValueError('Original measured worker PID required')
                validate(model_receipt,model_requirement,task,pid=measurement.pid)
                if model_requirement.get('schema')==VERIFIED_SCHEMA:outcome['model_receipt']=model_receipt
            if measurement.exit_code:return outcome
            payload, media = package_artifacts(directory, max_bytes=protocol.MAX_BYTES)
            protocol.validate_payload(payload, media)
        except (ValueError, OSError):
            if model_requirement is not None and model_requirement.get('schema')==VERIFIED_SCHEMA and 'model_receipt' not in outcome:
                raise WorkerUncertain('Original checkpoint load/rights evidence missing; retain assignment') from None
            return outcome
        extra={'model_receipt':model_receipt} if model_receipt is not None else {}
        return extra | {'status': 'done', 'cpu_seconds': outcome['cpu_seconds'], 'media_type': media,
                'result_b64': base64.b64encode(payload).decode()}


def run_once(client, state_directory):
    directory = Path(state_directory).absolute()
    if not directory.exists():
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise ValueError('Private owner-only state directory required')
    fd = os.open(directory / 'worker.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a+b') as lock:
        info = os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Unsafe worker lock')
        locks.flock(lock.fileno(), locks.LOCK_EX)
        journal = directory / 'active.json'
        state = protocol.decode(private_file(journal)) if journal.exists() or journal.is_symlink() else {'phase': 'idle', 'binding': client.binding}
        if not isinstance(state, dict) or state.get('binding') != client.binding:
            raise WorkerUncertain('Worker authority, credential or TLS trust binding changed')
        if state.get('phase') == 'dispatched':
            raise WorkerUncertain('Original worker execution uncertain; never automatically replay')
        if state.get('phase') in ('idle', 'done'):
            state = {'binding': client.binding, 'phase': 'requesting', 'instance': secrets.token_hex(16)}
            _write(journal, state)
        if state['phase'] == 'requesting':
            result = client.call('claim', {'instance': state['instance']})
            if not isinstance(result, dict) or set(result) != {'task'}:
                raise ValueError('Invalid claim acknowledgement')
            if result['task'] is None:
                _write(journal, {'phase': 'idle', 'binding': client.binding})
                return False
            _task(result['task'], state['instance'])
            state.update(phase='claimed', task=result['task'])
            _write(journal, state)
        if state['phase'] == 'claimed':
            try:
                outcome = _run(client, journal, state)
            except (ValueError, OSError):
                if state['phase'] == 'dispatched':
                    raise
                outcome = {'status': 'failed', 'cpu_seconds': None, 'media_type': None, 'result_b64': ''}
            state['task'] = {k: state['task'][k] for k in ('job_id', 'instance', 'nonce')}
            state.update(phase='ready', outcome=outcome)
            _write(journal, state)
        if state['phase'] != 'ready':
            raise WorkerUncertain('Unknown worker journal phase')
        task = state['task']
        result = client.call('complete', {'instance': state['instance'], 'nonce': task['nonce'], 'outcome': state['outcome']}, job=task['job_id'])
        if not isinstance(result, dict) or result != {'job_id': task['job_id'], 'acknowledged': True}:
            raise WorkerUncertain('Exact immutable completion acknowledgement required')
        _write(journal, {'phase': 'done', 'binding': client.binding})
        return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--poll-seconds', type=int, default=3)
    args = parser.parse_args(argv)
    try:
        if sys.platform != 'linux' or not 1 <= args.poll_seconds <= 60:
            raise ValueError('Linux worker and bounded polling required')
        config = protocol.decode(private_file(args.config, limit=16384))
        if not isinstance(config, dict) or set(config) - {'url', 'credential', 'ca_file'} or not {'url', 'credential'} <= set(config):
            raise ValueError('Invalid private worker configuration')
        client = WorkerClient(**config)
        while True:
            run_once(client, args.state)
            if not args.watch:
                return 0
            time.sleep(args.poll_seconds)
    except (WorkerUncertain, ValueError, KeyError, TypeError):
        print('Worker stopped: configuration or uncertain ownership requires operator review', file=sys.stderr)
        return 78
    except WorkerHTTP as exc:
        print(str(exc), file=sys.stderr)
        return 78 if exc.status in (301,302,303,307,308,400,401,403,404,409) else 1
    except (OSError, RuntimeError):
        print('Worker transport/execution unavailable; journal retained', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
