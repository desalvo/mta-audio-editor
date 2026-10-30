"""One Linux subreaper per worker tree, independent of the calling supervisor.

Only kernel ECHILD after adoption/reaping proves quiescence. Proc samples find
live children to stop, never certify an empty tree. Signals use pinned pidfds.
No process-global subreaper or wait(-1) is installed in the web server.
"""
import ctypes
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import uuid

LIMIT = 262144


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n'


def _send(fd, data):
    while data:
        data = data[os.write(fd, data):]


def _status(path):
    return dict(line.split(':', 1) for line in path.read_text().splitlines() if ':' in line)


def _children():
    own = _status(Path('/proc/self/status'))
    parent = int(own['Pid'])
    depth = len(own['NSpid'].split()) - 1
    result = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            value = _status(entry / 'status')
            if int(value['PPid']) == parent:
                ids = value['NSpid'].split()
                if len(ids) <= depth:
                    raise RuntimeError('Worker child namespace cannot be resolved')
                result.append((int(ids[depth]), entry, parent))
        except FileNotFoundError:
            continue
    return result


def _subreaper():
    if sys.platform != 'linux' or not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('Linux subreaper and pidfd support required')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0):
        raise OSError(ctypes.get_errno(), 'Cannot enable worker subreaper')
    value = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(value), 0, 0, 0) or value.value != 1:
        raise RuntimeError('Worker subreaper was not enabled')
    fd = os.pidfd_open(os.getpid())
    try:
        signal.pidfd_send_signal(fd, 0)
    finally:
        os.close(fd)
    _children()


def _stop_children():
    for pid, entry, parent in _children():
        try:
            fd = os.pidfd_open(pid)
        except ProcessLookupError:
            continue
        try:
            # Recheck direct parentage after pinning the process. A recycled
            # number can never redirect a signal from the original pidfd.
            if int(_status(entry / 'status')['PPid']) == parent:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
        except (FileNotFoundError, ProcessLookupError):
            pass
        finally:
            os.close(fd)


def _reap(leader, state):
    while True:
        try:
            pid, status, usage = os.wait4(-1, os.WNOHANG)
        except ChildProcessError:
            return True
        if not pid:
            return False
        state['cpu'] += usage.ru_utime + usage.ru_stime
        state['reaped'] += 1
        if pid == leader:
            state['exit_code'] = os.waitstatus_to_exitcode(status)


def _finish_tree(leader, state):
    deadline = time.monotonic() + 10
    while not _reap(leader, state):
        _stop_children()
        if time.monotonic() >= deadline:
            raise RuntimeError('Worker tree cannot be proven empty')
        time.sleep(.01)


def _guardian(control, reply, scope):
    state = {'cpu': 0., 'reaped': 0, 'exit_code': None}
    leader = None
    reason = 'not_started'
    started = time.monotonic()
    try:
        _subreaper()
        _send(reply, _encode({'ready': True, 'pid': os.getpid()}))
        with os.fdopen(os.dup(control), 'rb', buffering=0) as stream:
            raw = stream.readline(LIMIT + 1)
        if not raw:
            return
        if len(raw) > LIMIT or not raw.endswith(b'\n'):
            raise ValueError('Invalid guarded worker command')
        config = json.loads(raw)
        if (set(config) != {'argv', 'cwd', 'env', 'timeout', 'durable'}
                or not isinstance(config['argv'], list) or not config['argv']
                or not all(isinstance(x, str) and x for x in config['argv'])
                or not isinstance(config['env'], (dict, type(None)))
                or type(config['timeout']) not in (int, float) or not math.isfinite(config['timeout'])
                or not 0 < config['timeout'] <= 86400 or type(config['durable']) is not bool):
            raise ValueError('Invalid guarded worker command')
        if config['durable']:
            from app.worker_process_guard import launch
            process = launch(scope, config)
        else:
            process = subprocess.Popen(config['argv'], cwd=config['cwd'], env=config['env'],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True, close_fds=True)
        leader = process.pid
        reason = 'completed'
        _send(reply, _encode({'started': True, 'pid': leader}))
        with selectors.DefaultSelector() as selector:
            selector.register(control, selectors.EVENT_READ)
            while True:
                if _reap(leader, state) or state['exit_code'] is not None:
                    break
                if time.monotonic() - started >= config['timeout']:
                    reason = 'timeout'
                    break
                if selector.select(.02):
                    reason = 'supervisor_lost' if not os.read(control, 1024) else 'cancelled'
                    break
    finally:
        _finish_tree(leader, state)
        if scope:
            from app.worker_process_guard import quiescent
            quiescent(scope, reason=reason)
        result = {'empty': True, 'reason': reason, 'pid': leader,
                  'exit_code': state['exit_code'], 'cpu_seconds': state['cpu'],
                  'reaped': state['reaped'], 'elapsed': time.monotonic() - started}
        try:
            _send(reply, _encode(result))
        except BrokenPipeError:
            pass


def run(argv, *, cwd, timeout_seconds=3600, cancel_check=None, env=None, owner_receipt=None):
    """One process tree; original optional ledger scope survives caller death."""
    from .ai_metering_agent import Measurement, WorkerInterrupted, WorkerNotStarted, WorkerUncertain
    if (not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv)
            or type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 86400):
        raise ValueError('Invalid guarded worker arguments')
    if cancel_check is not None:
        try:
            cancelled = cancel_check()
        except Exception as exc:
            raise WorkerNotStarted(str(exc)) from exc
        if cancelled:
            raise WorkerNotStarted('AI worker cancelled before execution', cancelled=True)
    scope = uuid.uuid4().hex if owner_receipt else ''
    guard_env = dict(os.environ)
    if owner_receipt:
        from . import auth
        guard_env['MTA_DATA_DIR'] = str(auth.data_root())
    control_r, control_w = os.pipe()
    reply_r, reply_w = os.pipe()
    process = None
    launched = False
    try:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
            str(control_r), str(reply_w), scope], env=guard_env, pass_fds=(control_r, reply_w),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True)
        os.close(control_r); control_r = -1
        os.close(reply_w); reply_w = -1
        os.set_blocking(reply_r, False)
        buffer = b''
        messages = []
        cancelled = False
        callback_error = None
        deadline = time.monotonic() + 15
        final = None
        requested = False
        leader_pid = None
        from .ai_queue_usage import CpuProgress, process_cpu
        live_cpu = CpuProgress(env)
        with selectors.DefaultSelector() as selector:
            selector.register(reply_r, selectors.EVENT_READ)
            while final is None:
                if selector.select(.05):
                    chunk = os.read(reply_r, 8192)
                    if not chunk:
                        raise WorkerUncertain('Worker guardian exited without complete tree evidence')
                    buffer += chunk
                    if len(buffer) > 16384:
                        raise WorkerUncertain('Invalid worker guardian evidence')
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        messages.append(json.loads(line))
                for message in messages:
                    if message.get('ready') is True:
                        if message.get('pid') != process.pid:
                            raise WorkerUncertain('Original worker guardian identity mismatch')
                        if owner_receipt:
                            from .worker_process_guard import register
                            register(scope, process.pid, owner_receipt)
                        payload = _encode({'argv': argv, 'cwd': str(cwd), 'env': env,
                            'timeout': timeout_seconds, 'durable': bool(owner_receipt)})
                        if len(payload) > LIMIT:
                            raise ValueError('Oversized guarded worker command')
                        _send(control_w, payload)
                        requested = True
                        deadline = time.monotonic() + timeout_seconds + 20
                    elif message.get('started') is True:
                        launched = True
                        leader_pid = message['pid']
                    elif 'empty' in message:
                        final = message
                messages.clear()
                if final is not None:
                    break
                if cancel_check is not None and not cancelled:
                    try:
                        cancelled = bool(cancel_check())
                    except Exception as exc:
                        callback_error = exc; cancelled = True
                    if cancelled:
                        if not requested:
                            raise WorkerNotStarted('AI worker cancelled before execution', cancelled=True)
                        _send(control_w, b'cancel\n')
                if leader_pid is not None:
                    live_cpu.publish(lambda: process_cpu(leader_pid))
                if time.monotonic() > deadline:
                    raise WorkerUncertain('Worker guardian tree evidence unavailable')
        process.wait(timeout=5)
        if (process.returncode or final.get('empty') is not True or type(final.get('pid')) is not int
                or type(final.get('cpu_seconds')) not in (int, float)
                or not math.isfinite(final['cpu_seconds']) or final['cpu_seconds'] < 0
                or type(final.get('exit_code')) is not int):
            raise WorkerUncertain('Worker guardian tree evidence is incomplete')
        measurement = Measurement(-1 if final['reason'] == 'timeout' else final['exit_code'],
            final['elapsed'], {'cpu_seconds': final['cpu_seconds']}, 'worker', True,
            pid=final['pid'], tree_complete=True)
        if callback_error is not None:
            raise WorkerInterrupted(measurement) from callback_error
        if cancelled or final['reason'] == 'cancelled':
            raise WorkerInterrupted(measurement)
        return measurement
    except OSError as exc:
        if not launched and process is None:
            raise WorkerNotStarted('AI worker guardian could not start') from exc
        raise WorkerUncertain('Worker guardian communication failed') from exc
    finally:
        for fd in (control_r, control_w, reply_r, reply_w):
            if fd >= 0:
                os.close(fd)
        # EOF requests cleanup. Never kill a guardian with unverified children.
        if process is not None and process.poll() is None:
            try:
                process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                pass


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    _guardian(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
