"""Process-isolated CPU metering for trusted AI subprocess workers.

Uses wait4 for the exact child PID. Deliberately leaves GPU consumption unset:
process-level GPU telemetry requires a GPU-specific trusted sensor and workload
isolation. Shared host GPU utilisation is NOT attributable to a user.
"""
from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class Measurement:
    exit_code: int
    elapsed_seconds: float
    usage: dict[str, float]
    source: str
    isolated: bool = True
    gpu_diagnostics: dict[str, float] | None = None


def _io(pid: int) -> tuple[int, int] | None:
    """Read Linux /proc per-PID physical block IO, if accessible."""
    try:
        pairs = {}
        for line in Path(f'/proc/{pid}/io').read_text().splitlines():
            key, _, value = line.partition(':')
            if key in {'read_bytes', 'write_bytes'}:
                pairs[key] = int(value.strip())
        if len(pairs) != 2:
            return None
        return pairs['read_bytes'], pairs['write_bytes']
    except (OSError, ValueError):
        return None


def _descendants(parent_pid: int) -> set[int]:
    """Return observed descendants using per-PID PPid fields, never host load counters."""
    ppid = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / 'status').read_text()
            parent = next(int(line.split(':', 1)[1].strip()) for line in status.splitlines() if line.startswith('PPid:'))
            ppid[int(entry.name)] = parent
        except (OSError, ValueError, StopIteration):
            continue
    found = {parent_pid}
    for _ in range(len(ppid)):
        more = {pid for pid, parent in ppid.items() if parent in found}
        if more <= found:
            break
        found |= more
    found.discard(parent_pid)
    return found


def run_metered_process(argv: list[str], *, cwd: str, timeout_seconds: int = 3600) -> Measurement:
    """Run a fixed operator-selected executable and attribute direct-child CPU.

    No shell or user-provided command strings are accepted by this function's
    callers. Worker child processes must be separately instrumented; only the
    directly reaped process is metered. Requires Unix wait4 (Linux server).
    """
    if os.name != 'posix' or not hasattr(os, 'wait4'):
        raise RuntimeError('Linux wait4 metering required')
    if not argv or not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        raise ValueError('Invalid process arguments')
    if timeout_seconds <= 0 or timeout_seconds > 86400:
        raise ValueError('Invalid timeout')
    started = time.monotonic()
    proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)  # noqa: S603 -- operator-controlled executable only
    max_io = _io(proc.pid)
    timed_out = False
    detected_descendants = False
    try:
        while True:
            pid, status, rusage = os.wait4(proc.pid, os.WNOHANG)
            if pid == proc.pid:
                break
            # wait4 and /proc/<pid>/io cover the direct child only. If it
            # creates other processes, do not pretend the account is complete.
            if _descendants(proc.pid):
                detected_descendants = True
            current = _io(proc.pid)
            if current:
                max_io = tuple(max(a, b) for a, b in zip(max_io, current)) if max_io else current
            if time.monotonic() - started >= timeout_seconds:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                _, status, rusage = os.wait4(proc.pid, 0)
                break
            time.sleep(0.05)
    finally:
        # The direct child may exit while its descendants remain in the
        # separate process group. Stop those descendants even after a normal
        # parent exit; do not leave unmetered inference running.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        # If sampling itself raised, reap the leader to avoid zombies.
        if 'status' not in locals():
            try:
                _, status, rusage = os.wait4(proc.pid, 0)
            except ChildProcessError:
                pass
        proc.returncode = os.waitstatus_to_exitcode(status) if 'status' in locals() else None
    elapsed = max(0.0, time.monotonic() - started)
    usage = {'cpu_seconds': max(0.0, rusage.ru_utime + rusage.ru_stime)}
    if max_io:
        usage['disk_read_bytes'] = float(max_io[0])
        usage['disk_write_bytes'] = float(max_io[1])
    return Measurement(-1 if timed_out else proc.returncode, elapsed, usage, 'worker', not detected_descendants)


def execute_registered_worker(user_id: int, kind: str, plan: dict, *, token_id=None,
                              timeout_seconds: int = 1200, source_wav: bytes | None = None) -> tuple[bytes, dict]:
    """Run the administrator-installed AI worker and persist measured usage.

    Unsupported GPU/process-tree telemetry is omitted, not guessed. Output is
    returned to the caller without changing billing for model files shared
    by multiple users.
    """
    import json
    import sys
    import tempfile
    from . import ai_billing
    from .ai_worker_protocol import verify_preview_wav, WorkerUnavailable, MAX_REQUEST_BYTES
    from .ai_worker_registry import resolve_worker
    from .ai_worker_artifacts import package_artifacts

    worker = resolve_worker(kind)
    if worker is None:
        raise WorkerUnavailable('No trusted AI worker configured')
    if source_wav is not None and ('source_audio' in plan or 'input_path' in plan):
        raise ValueError('Audio path must be generated by MTA')
    encoded = json.dumps(plan, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError('AI plan exceeds size limit')
    job_id = ai_billing.create_job(user_id, kind, token_id)
    # Only operator-enabled GPU adapters obtain logical slots; neither the
    # request plan nor the remote user may declare GPU eligibility.
    from .ai_gpu_slot_accounting import slot_enabled_for_kind
    gpu_slot_enabled = slot_enabled_for_kind(kind)
    with tempfile.TemporaryDirectory(prefix='mta-meter-') as folder:
        directory = Path(folder)
        request_path = directory / 'request.json'
        output_path = directory / 'preview.wav'
        if source_wav is not None:
            from .ai_worker_protocol import verify_preview_wav
            input_path = directory / 'source.wav'
            input_path.write_bytes(source_wav)
            verify_preview_wav(input_path)
            input_path.chmod(0o400)
            encoded = json.dumps({**plan, 'source_audio': str(input_path)}, ensure_ascii=False, allow_nan=False).encode('utf-8')
        request_path.write_bytes(encoded)
        request_path.chmod(0o600)
        args = ([sys.executable, str(worker)] if worker.suffix == '.py' else [str(worker)])
        args += ['--request', str(request_path), '--output', str(output_path)]
        result = None
        gpu_slot_acquired = False
        try:
            if gpu_slot_enabled:
                from . import ai_gpu_slot_accounting as gpu_slots
                gpu_slots.acquire(job_id, os.getenv('MTA_AI_GPU_LOGICAL_DEVICE', 'gpu0'))
                gpu_slot_acquired = True
            if os.getenv('MTA_AI_CGROUP_PARENT'):
                from .ai_cgroup_metering import run_cgroup_process
                result = run_cgroup_process(args, cwd=folder, timeout_seconds=timeout_seconds)
            else:
                result = run_metered_process(args, cwd=folder, timeout_seconds=timeout_seconds)
            if result.exit_code:
                raise WorkerUnavailable('AI worker failed or timed out')
            payload, media_type = package_artifacts(directory)
            info = {"format": "wav" if media_type == "audio/wav" else "artifact-zip"}
            usage = {key: value for key, value in result.usage.items() if key not in ('disk_read_bytes', 'disk_write_bytes')}
            # Transient worker I/O is diagnostic only, never billable disk use.
            # The output may already be counted in /proc/<pid>/io. Never add
            # its size a second time as if it were extra physical disk I/O.
            if gpu_slot_acquired:
                gpu_slots.release(job_id)
                gpu_slot_acquired = False
            ai_billing.finish_job(job_id, 'done', usage if result.isolated else None,
                                  source=result.source if result.isolated else 'unmetered')
            return payload, {'job_id': job_id, 'audio': info, 'usage': usage,
                             'gpu_metered': False, 'process_tree_metered': result.isolated,
                             'gpu_diagnostics': result.gpu_diagnostics or {}, 'media_type': media_type}
        except BaseException:
            if gpu_slot_acquired:
                # Do not silently finalize a job if its lease cannot be
                # accounted for. Recovery must reconcile it explicitly.
                gpu_slots.release(job_id, aborted=True)
                gpu_slot_acquired = False
            if result is None:
                ai_billing.finish_job(job_id, 'failed', source='unmetered')
            else:
                ai_billing.finish_job(job_id, 'failed', result.usage if result.isolated else None,
                                      source=result.source if result.isolated else 'unmetered')
            raise
