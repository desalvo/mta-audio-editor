"""Fail-closed per-job cgroup v2 CPU and I/O accounting on Linux.

The operator must delegate a writable cgroup v2 subtree using
MTA_AI_CGROUP_PARENT. CPU and disk I/O counters cover *only* that cgroup,
including short-lived descendants. GPU/energy are intentionally not inferred
from host telemetry. The cgroup must be empty before measurements are valid.
"""
from __future__ import annotations

import logging
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from threading import Event, Thread, Lock

from .ai_metering_agent import Measurement

# The child enters the dedicated cgroup *before* exec'ing the worker. No
# preexec_fn (unsafe from a multithreaded server) and no shell are involved.
_CHILD = '''import os,sys
cg, cwd, exe, *args = sys.argv[1:]
try:
    with open(os.path.join(cg, "cgroup.procs"), "w") as f:
        f.write(str(os.getpid()))
    os.chdir(cwd)
    os.execvpe(exe, [exe, *args], os.environ)
except BaseException as ex:
    print("AI cgroup launch failed: " + str(ex), file=sys.stderr)
    sys.exit(125)
'''



_LOG = logging.getLogger(__name__)
_ERROR_TAIL_LIMIT = 8192


class _BoundedStderr:
    """Drain worker stderr without blocking, retaining only a bounded tail."""

    def __init__(self, stream):
        self._stream = stream
        self._lock = Lock()
        self._tail = b''
        self._thread = Thread(target=self._drain, name='mta-ai-worker-stderr', daemon=True)
        self._thread.start()

    def _drain(self):
        try:
            while True:
                data = self._stream.read(4096)
                if not data:
                    break
                with self._lock:
                    self._tail = (self._tail + data)[-_ERROR_TAIL_LIMIT:]
        except OSError:
            pass
        finally:
            self._stream.close()

    def finish(self) -> str:
        self._thread.join(timeout=2)
        with self._lock:
            return self._tail.decode('utf-8', errors='replace')


def _safe_worker_error(stderr: str) -> str:
    """Return a restricted diagnostic; never log arbitrary stderr verbatim."""
    lines = []
    for raw in stderr.splitlines()[-15:]:
        # Keep exception identity and common runtime errors; do not reproduce
        # user prompts, request bodies, traceback file paths or credential dumps.
        match = re.match(r'^([\w.]+(?:Error|Exception|Warning)|RuntimeError|OSError|Exception):\s*(.*)$', raw.strip())
        if match:
            detail = match.group(2)
            detail = re.sub(r'(?i)(password|token|secret|api[_-]?key|authorization)\s*[=:]\s*\S+', r'\1=[REDACTED]', detail)
            detail = re.sub(r'https?://\S+', '[URL]', detail)
            detail = re.sub(r'\b[A-Za-z0-9_\-]{48,}\b', '[REDACTED]', detail)
            lines.append((match.group(1) + ': ' + detail)[:300])
    return ' | '.join(lines[-3:]) if lines else 'no safe exception detail in stderr'


def _worker_failure(stderr: str, exit_code: int) -> dict:
    """Allowlisted classifications only: never persist user-controlled messages."""
    category = 'worker_exit'
    for marker, code in (
        ('attempted relative import with no known parent package', 'worker_import_context'),
        ('ModuleNotFoundError:', 'worker_dependency_missing'),
        ('AI cgroup launch failed:', 'cgroup_launch_failed'),
        ('Connection refused', 'ace_connection_refused'),
        ('HTTP Error 401', 'ace_unauthorized'),
        ('HTTP Error 403', 'ace_forbidden'),
        ('HTTP Error 404', 'ace_endpoint_missing'),
        ('ACE-Step generation timed out', 'ace_generation_timeout'),
        ('ACE-Step adapter error:', 'ace_adapter_failed'),
    ):
        if marker in stderr:
            category = code
            break
    return {'schema': 'mta-worker-failure-v1', 'category': category,
            'exit_code': exit_code, 'metering_valid': False}


def _cpu(path: Path) -> float:
    values = dict(line.split()[:2] for line in (path / 'cpu.stat').read_text().splitlines() if len(line.split()) >= 2)
    if 'usage_usec' not in values:
        raise RuntimeError('cgroup cpu.stat has no usage_usec')
    return int(values['usage_usec']) / 1_000_000.0


def _io(path: Path) -> tuple[float, float]:
    reads = writes = 0
    for line in (path / 'io.stat').read_text().splitlines():
        for item in line.split()[1:]:
            key, sep, val = item.partition('=')
            if not sep:
                continue
            if key == 'rbytes': reads += int(val)
            if key == 'wbytes': writes += int(val)
    return float(reads), float(writes)


def _assert_empty(path: Path) -> None:
    """Require the kernel's recursive populated flag to be zero.

    cgroup.procs only enumerates direct members, not processes remaining in
    nested cgroups. Charging a completed job with nested workers is unsafe.
    """
    entries = dict(line.split(None, 1) for line in (path / 'cgroup.events').read_text().splitlines() if ' ' in line)
    if entries.get('populated') != '0':
        raise RuntimeError('AI job cgroup still contains processes or descendants')


def _pids(path: Path) -> list[int]:
    return [int(x) for x in (path / 'cgroup.procs').read_text().split()]


def run_cgroup_process(argv: list[str], *, cwd: str, timeout_seconds: int = 3600, parent: str | None = None, cancel_event: Event | None = None, cancel_check=None, env: dict[str, str] | None = None) -> Measurement:
    """Execute an operator-selected worker in an isolated delegated cgroup.

    Raises instead of returning guessed values if group telemetry is missing.
    No host-level metrics are used. The caller must mark failures unmetered.
    """
    if sys.platform != 'linux':
        raise RuntimeError('cgroup v2 accounting requires Linux')
    if not argv or not all(isinstance(a, str) and a for a in argv):
        raise ValueError('Invalid worker command')
    if not 0 < timeout_seconds <= 86400:
        raise ValueError('Invalid timeout')
    # An already-cancelled request must not allocate a cgroup or start a child.
    if (cancel_event is not None and cancel_event.is_set()) or (cancel_check is not None and cancel_check()):
        raise RuntimeError('AI worker cancelled; metering invalid')
    parent_str = parent or os.getenv('MTA_AI_CGROUP_PARENT', '')
    if not parent_str:
        raise RuntimeError('MTA_AI_CGROUP_PARENT not configured')
    root = Path(parent_str).resolve(strict=True)
    if not root.is_relative_to(Path('/sys/fs/cgroup')) or root == Path('/sys/fs/cgroup'):
        raise RuntimeError('Accounting requires a delegated /sys/fs/cgroup subtree')
    if (Path('/sys/fs/cgroup') / 'cgroup.controllers').exists() is False:
        raise RuntimeError('cgroup v2 not mounted')
    if not root.is_dir() or not os.access(root, os.W_OK):
        raise RuntimeError('No writable delegated cgroup')
    controllers = set((root / 'cgroup.controllers').read_text().split())
    enabled = set((root / 'cgroup.subtree_control').read_text().split())
    if not {'cpu', 'io'} <= controllers or not {'cpu', 'io'} <= enabled:
        raise RuntimeError('Dedicated AI cgroup requires delegated cpu and io controllers')
    job_group = root / ('mta-' + uuid.uuid4().hex)
    job_group.mkdir(mode=0o700)
    proc = None
    stderr_reader = None
    started = time.monotonic()
    try:
        # Only take before/after measurements from the isolated job group.
        _cpu(job_group)
        _io(job_group)
        _assert_empty(job_group)
        # Cancellation can arrive during delegated cgroup setup.
        if (cancel_event is not None and cancel_event.is_set()) or (cancel_check is not None and cancel_check()):
            raise RuntimeError('AI worker cancelled; metering invalid')
        proc = subprocess.Popen([sys.executable, '-c', _CHILD, str(job_group), cwd, *argv],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, start_new_session=True, env=env)
        stderr_reader = _BoundedStderr(proc.stderr)
        # Optional best-effort per-job diagnostic snapshots. These are never
        # returned as certified gpu_seconds or used in billing: polling can
        # miss short-lived GPU clients and driver fdinfo support varies.
        gpu_observed: dict[tuple[int, str], int] = {}
        gpu_peak_memory_kib: dict[str, int] = {}
        if os.getenv('MTA_AI_DRM_DIAGNOSTICS', '').lower() in ('1', 'true', 'yes'):
            from .ai_gpu_process_meter import cgroup_gpu_detailed_snapshot
            gpu_diagnostics_enabled = True
        else:
            gpu_diagnostics_enabled = False
        while proc.poll() is None:
            if (cancel_event is not None and cancel_event.is_set()) or (cancel_check is not None and cancel_check()):
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait()
                raise RuntimeError('AI worker cancelled; metering invalid')
            if time.monotonic() - started >= timeout_seconds:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait()
                raise TimeoutError('AI worker timed out; metering invalid')
            if gpu_diagnostics_enabled:
                try:
                    snap = cgroup_gpu_detailed_snapshot(job_group)
                    current_memory: dict[str, int] = {}
                    for pid, reading in snap.items():
                        for name, kib in reading.memory_kib.items():
                            current_memory[name] = current_memory.get(name, 0) + kib
                        for engine, ns in reading.engine_ns.items():
                            key = (pid, engine)
                            gpu_observed[key] = max(gpu_observed.get(key, 0), ns)
                    for name, kib in current_memory.items():
                        gpu_peak_memory_kib[name] = max(gpu_peak_memory_kib.get(name, 0), kib)
                except (RuntimeError, OSError, ValueError):
                    # Missing samples must not create a billable GPU measure.
                    pass
            time.sleep(0.05)
        proc.wait()
        # An exit observed between polling iterations must not settle a
        # cancelled job as successful and billable.
        if (cancel_event is not None and cancel_event.is_set()) or (cancel_check is not None and cancel_check()):
            raise RuntimeError('AI worker cancelled; metering invalid')
        # Child processes may continue after the original process exits.
        remaining = _pids(job_group)
        if remaining:
            # Do not bill an unfinished group; forcibly cancel its descendants.
            for pid in remaining:
                try: os.kill(pid, signal.SIGKILL)
                except ProcessLookupError: pass
            raise RuntimeError('AI worker left running descendants; metering invalid')
        _assert_empty(job_group)
        if proc.returncode != 0:
            detail = stderr_reader.finish() if stderr_reader is not None else ''
            failure = _worker_failure(detail, proc.returncode)
            _LOG.error('AI metered worker exited nonzero (pid=%s, exit_code=%s): %s',
                       proc.pid, proc.returncode, _safe_worker_error(detail),
                       extra={'mta_worker_failure': failure})
            raise RuntimeError(
                f'AI worker failed (exit code {proc.returncode}); metering invalid; '
                f'diagnostic: {failure["category"]}; check server diagnostics and journal')
        cpu = _cpu(job_group)
        read_bytes, write_bytes = _io(job_group)
        if (cancel_event is not None and cancel_event.is_set()) or (cancel_check is not None and cancel_check()):
            raise RuntimeError('AI worker cancelled; metering invalid')
        return Measurement(0, max(0, time.monotonic() - started),
                           {'cpu_seconds': cpu, 'disk_read_bytes': read_bytes,
                            'disk_write_bytes': write_bytes}, 'cgroup', True,
                           {'observed_engine_seconds': sum(gpu_observed.values()) / 1e9,
                            'observed_peak_memory_kib': gpu_peak_memory_kib,
                            'billable': False, 'coverage': 'sampled_process_fdinfo_only'}
                           if gpu_diagnostics_enabled else None)
    finally:
        if proc is not None and proc.poll() is None:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait()
        if stderr_reader is not None:
            stderr_reader.finish()
        # A non-empty cgroup cannot be removed. Kill remaining children and
        # refuse to return a metered result when cleanup is incomplete.
        try:
            for pid in _pids(job_group):
                try: os.kill(pid, signal.SIGKILL)
                except ProcessLookupError: pass
            for _ in range(15):
                try:
                    job_group.rmdir()
                    break
                except OSError:
                    time.sleep(0.05)
        except OSError:
            pass
