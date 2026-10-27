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
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from threading import Event, Lock
from .service_admission import worker_thread as Thread

from .ai_metering_agent import Measurement

# The child enters the dedicated cgroup *before* exec'ing the worker. No
# preexec_fn (unsafe from a multithreaded server) and no shell are involved.
_CHILD = '''import os,sys
cg, cwd, scope, package_root, exe, *args = sys.argv[1:]
try:
    if scope:
        sys.path.insert(0, package_root)
        from app.worker_cgroup_recovery import enter_before_exec
        enter_before_exec(scope, cg)
    else:
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
    # Nested Demucs/SAM subprocess tracebacks can put more than 15 frames
    # between the original exception and CalledProcessError. Scan the bounded
    # tail, retaining only the same restricted exception summaries below.
    for raw in stderr[-_ERROR_TAIL_LIMIT:].splitlines():
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


_EXCEPTION_TYPES = frozenset({'ImportError', 'ModuleNotFoundError', 'RuntimeError', 'ValueError',
    'TypeError', 'AttributeError', 'OSError', 'PermissionError', 'FileNotFoundError',
    'CalledProcessError', 'OutOfMemoryError', 'NotImplementedError', 'AssertionError'})
_DEPENDENCIES = frozenset({'torch', 'torchaudio', 'torchcodec', 'demucs', 'soundfile', 'whisper',
    'audio_separator', 'numpy', 'sam_audio'})
_FAILURE_MARKERS = (
    ('MTA_BACKING_FAILURE:rocm_conversion_failed', 'backing_rocm_conversion_failed'),
    ('MTA_BACKING_FAILURE:unsupported_mdx_runtime', 'backing_runtime_incompatible'),
    ("BaseModel._from_pretrained() missing 2 required keyword-only arguments: 'proxies' and 'resume_download'", 'sam_hub_incompatible'),
    ('MTA_SAM_FAILURE:imports', 'sam_dependency_failed'),
    ('MTA_SAM_FAILURE:model_load', 'sam_model_load_failed'),
    ('MTA_SAM_FAILURE:processor_load', 'sam_processor_load_failed'),
    ('MTA_SAM_FAILURE:audio_processing', 'sam_audio_processing_failed'),
    ('MTA_SAM_FAILURE:inference', 'sam_inference_failed'),
    ('MTA_SAM_FAILURE:audio_save', 'sam_audio_save_failed'),

    ('Worker outputs exceed artifact size limit', 'worker_output_size_limit'),
    ('TorchCodec is required', 'worker_audio_codec_missing'),
    ("No module named 'torchcodec'", 'worker_audio_codec_missing'),
    ('Could not load libtorchcodec', 'worker_audio_codec_unavailable'),

    ('attempted relative import with no known parent package', 'worker_import_context'),
    ('ModuleNotFoundError:', 'worker_dependency_missing'),
    ('ROCm requested but unavailable', 'worker_rocm_unavailable'),
    ('Expected one of cpu, cuda', 'worker_invalid_device'),
    ('torch.OutOfMemoryError:', 'worker_out_of_memory'),
    ('AI cgroup launch failed:', 'cgroup_launch_failed'),
    ('Connection refused', 'ace_connection_refused'),
    ('HTTP Error 401', 'ace_unauthorized'),
    ('HTTP Error 403', 'ace_forbidden'),
    ('HTTP Error 404', 'ace_endpoint_missing'),
    ('ACE-Step backend generation timeout', 'ace_backend_timeout'),
    ('ACE-Step backend GPU out of memory', 'ace_gpu_out_of_memory'),
    ('ACE-Step generation failed', 'ace_backend_failed'),
    ('ACE-Step task control request rejected', 'ace_control_rejected'),
    ('ACE-Step generation timed out', 'ace_generation_timeout'),
    ('ACE-Step adapter error:', 'ace_adapter_failed'),
)
FAILURE_CATEGORIES = frozenset({'worker_exit', *(code for _, code in _FAILURE_MARKERS)})


def _worker_failure(stderr: str, exit_code: int) -> dict:
    """Only fixed codes/types/dependency names; no arbitrary worker messages."""
    category = next((code for marker, code in _FAILURE_MARKERS if marker in stderr), 'worker_exit')
    document = {'schema': 'mta-worker-failure-v1', 'category': category,
                'exit_code': exit_code, 'metering_valid': False}
    kinds = []
    for name in re.findall(r'^([\w.]+):', stderr, flags=re.MULTILINE):
        name = name.rsplit('.', 1)[-1]
        if name in _EXCEPTION_TYPES and name not in kinds:
            kinds.append(name)
    if kinds:
        document['exception_types'] = kinds[-3:]
    for name in re.findall(r"No module named ['\"]([\w.]+)['\"]", stderr):
        name = name.split('.')[0]
        if name in _DEPENDENCIES:
            document['missing_dependency'] = name
            break
    return document


def safe_failure_metadata(failure):
    if (not isinstance(failure, dict) or failure.get('schema') != 'mta-worker-failure-v1'
            or not isinstance(failure.get('category'), str) or failure.get('category') not in FAILURE_CATEGORIES
            or type(failure.get('exit_code')) is not int):
        return None
    result = {key: failure[key] for key in ('category', 'exit_code')}
    result['metering_valid'] = False
    kinds = failure.get('exception_types')
    if isinstance(kinds, list) and 1 <= len(kinds) <= 3 and all(isinstance(v, str) and v in _EXCEPTION_TYPES for v in kinds):
        result['exception_types'] = kinds
    if isinstance(failure.get('missing_dependency'), str) and failure['missing_dependency'] in _DEPENDENCIES:
        result['missing_dependency'] = failure['missing_dependency']
    return result



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


def _stop_cgroup(path: Path, *, timeout_seconds: float = 2.0) -> None:
    """Kill the entire kernel subtree and require recursive quiescence.

    PID lists and process groups miss nested cgroups/setsid descendants and
    can target recycled PIDs. Keep a failed group for operator inspection.
    This proof applies only to this local cgroup, never remote worker activity.
    """
    try:
        _assert_empty(path)
        return
    except RuntimeError:
        pass
    (path / 'cgroup.kill').write_text('1')
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            _assert_empty(path)
            return
        except RuntimeError:
            if time.monotonic() >= deadline:
                raise RuntimeError('AI cgroup quiescence remains unverified') from None
            time.sleep(0.02)


def run_cgroup_process(argv: list[str], *, cwd: str, timeout_seconds: int = 3600, parent: str | None = None, cancel_event: Event | None = None, cancel_check=None, env: dict[str, str] | None = None, owner_receipt: dict | None = None) -> Measurement:
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
    scope_id = None
    stderr_reader = None
    started = time.monotonic()
    try:
        # Only take before/after measurements from the isolated job group.
        _cpu(job_group)
        _io(job_group)
        _assert_empty(job_group)
        if not (job_group / 'cgroup.kill').is_file():
            raise RuntimeError('Recursive AI cancellation requires cgroup.kill')
        # Cancellation can arrive during delegated cgroup setup.
        if (cancel_event is not None and cancel_event.is_set()) or (cancel_check is not None and cancel_check()):
            raise RuntimeError('AI worker cancelled; metering invalid')
        from .deferred_execution_owner import cgroup_receipt
        active_owner=cgroup_receipt()
        if active_owner is not None and owner_receipt is not None and active_owner!=owner_receipt:
            raise RuntimeError('Worker cgroup ownership conflicts with active inference')
        owner_receipt=owner_receipt if owner_receipt is not None else active_owner
        if owner_receipt is not None:
            from .worker_cgroup_recovery import register
            scope_id = register(job_group, owner_receipt['job_id'], owner_receipt)
        proc = subprocess.Popen([sys.executable, '-c', _CHILD, str(job_group), cwd, scope_id or '', str(Path(__file__).resolve().parent.parent), *argv],
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
        from .ai_queue_usage import CpuProgress
        live_cpu = CpuProgress(env)
        while proc.poll() is None:
            live_cpu.publish(lambda: _cpu(job_group))
            if (cancel_event is not None and cancel_event.is_set()) or (cancel_check is not None and cancel_check()):
                _stop_cgroup(job_group)
                proc.wait(timeout=2)
                raise RuntimeError('AI worker cancelled; metering invalid')
            if time.monotonic() - started >= timeout_seconds:
                _stop_cgroup(job_group)
                proc.wait(timeout=2)
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
        try:
            _assert_empty(job_group)
        except RuntimeError:
            # Do not bill an unfinished group; forcibly cancel its descendants.
            _stop_cgroup(job_group)
            raise RuntimeError('AI worker left running descendants; metering invalid')
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
        # Stop a bootstrap still outside the cgroup before attesting cleanup.
        # Its transactional admission gate also refuses any committed receipt.
        if proc is not None and proc.poll() is None:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _LOG.error('AI worker exit remains unverified: %s', job_group.name)
        # Kernel subtree cancellation includes processes that changed session
        # or entered child cgroups. Never remove an unverified/nonempty group.
        quiescent = False
        try:
            _stop_cgroup(job_group)
            if scope_id is not None:
                from .worker_cgroup_recovery import owner_quiescent
                owner_quiescent(scope_id)
            quiescent = True
        except (OSError, RuntimeError, sqlite3.DatabaseError):
            _LOG.error('AI cgroup cleanup incomplete; quiescence unverified: %s', job_group.name)
        if stderr_reader is not None:
            stderr_reader.finish()
        if quiescent:
            try:
                # Empty descendants are removed bottom-up, never followed
                # outside the operator-delegated kernel hierarchy.
                for child in sorted(job_group.rglob('*'), key=lambda p: len(p.parts), reverse=True):
                    if child.is_dir() and not child.is_symlink():
                        child.rmdir()
                job_group.rmdir()
            except OSError:
                _LOG.warning('Empty AI cgroup retained for operator cleanup: %s', job_group.name)
        elif sys.exc_info()[0] is None:
            raise RuntimeError('AI cgroup cleanup failed; metering invalid')
