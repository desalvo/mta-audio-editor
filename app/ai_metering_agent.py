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
from typing import Callable


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


def run_metered_process(argv: list[str], *, cwd: str, timeout_seconds: int = 3600, cancel_check: Callable[[], bool] | None = None, env: dict | None = None) -> Measurement:
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
                            start_new_session=True, env=env)  # noqa: S603 -- operator-controlled executable only
    from .ai_queue_usage import CpuProgress, process_cpu
    live_cpu = CpuProgress(env)
    max_io = _io(proc.pid)
    timed_out = False
    cancelled = False
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
            live_cpu.publish(lambda: process_cpu(proc.pid))
            current = _io(proc.pid)
            if current:
                max_io = tuple(max(a, b) for a, b in zip(max_io, current)) if max_io else current
            if cancel_check is not None and cancel_check():
                cancelled = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                _, status, rusage = os.wait4(proc.pid, 0)
                break
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
    if cancelled:
        raise RuntimeError('AI worker cancelled during execution; result discarded')
    elapsed = max(0.0, time.monotonic() - started)
    usage = {'cpu_seconds': max(0.0, rusage.ru_utime + rusage.ru_stime)}
    if max_io:
        usage['disk_read_bytes'] = float(max_io[0])
        usage['disk_write_bytes'] = float(max_io[1])
    return Measurement(-1 if timed_out else proc.returncode, elapsed, usage, 'worker', not detected_descendants)


def _execute_registered_worker(user_id: int, kind: str, plan: dict, *, token_id=None,
                              timeout_seconds: int = 1200, source_wav: bytes | None = None,
                              cancel_check: Callable[[], bool] | None = None) -> tuple[bytes, dict]:
    """Run the administrator-installed AI worker and persist measured usage.

    Unsupported GPU/process-tree telemetry is omitted, not guessed. Output is
    returned to the caller without changing billing for model files shared
    by multiple users.
    """
    import json
    import tempfile
    from . import ai_billing
    from .ai_worker_protocol import verify_preview_wav, WorkerUnavailable, MAX_REQUEST_BYTES
    from .ai_worker_registry import resolve_worker
    from .ai_worker_artifacts import package_artifacts

    from .ai_worker_protocol import _ace_remote_cleanup as _ace_cleanup
    worker = resolve_worker(kind)
    if plan.get('kind',kind)!=kind:raise ValueError('AI plan cannot override the registered engine')
    plan={**plan,'kind':kind}
    if worker is None:
        raise WorkerUnavailable('No trusted AI worker configured')
    if source_wav is not None and ('source_audio' in plan or 'input_path' in plan):
        raise ValueError('Audio path must be generated by MTA')
    if source_wav is not None:
        from .ai_payload_limits import MAX_SOURCE_BYTES
        if not isinstance(source_wav, bytes) or not 0 < len(source_wav) <= MAX_SOURCE_BYTES:
            raise ValueError('AI source audio exceeds size limit or is empty')
    encoded = json.dumps(plan, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError('AI plan exceeds size limit')
    from .ai_global_execution import current_job
    from . import ai_arranger_runtime as queue
    # Freeze policy once. Later administrator changes cannot invalidate a
    # running job between backend publication and server-side packaging.
    artifact_limit_mib = queue.artifact_limit_mib()
    artifact_budget = artifact_limit_mib * 1024 * 1024
    queue_id=current_job.get();defer_settlement=False;job_id=None
    if queue_id:
        with queue._db() as con:queued=con.execute('SELECT operation FROM jobs WHERE job_id=?',(queue_id,)).fetchone()
        if queued and queued[0] in ('arranger','remix'):
            job_id=ai_billing.existing_inference_ledger_job(queue_id,user_id,queued[0])
            defer_settlement=job_id is not None
    job_id=job_id or ai_billing.create_job(user_id,kind,token_id)
    if queue_id:
        with ai_billing.db() as con:
            ai_billing._init(con);con.execute('UPDATE ai_compute_jobs SET queue_job_id=? WHERE id=?',(queue_id,job_id))
    # Only operator-enabled GPU adapters obtain logical slots; neither the
    # request plan nor the remote user may declare GPU eligibility.
    from .ai_gpu_slot_accounting import slot_enabled_for_kind
    gpu_slot_enabled = slot_enabled_for_kind(kind)
    from contextlib import nullcontext
    with tempfile.TemporaryDirectory(prefix='mta-meter-') as folder, (_ace_cleanup(plan, lambda: Path(folder)/'progress.json') if kind=='ace-step' else nullcontext()):
        directory = Path(folder)
        request_path = directory / 'request.json'
        output_path = directory / 'preview.wav'
        if source_wav is not None:
            from .ai_worker_protocol import verify_preview_wav
            input_path = directory / 'source.wav'
            input_path.write_bytes(source_wav)
            verify_preview_wav(input_path)
            input_path.chmod(0o400)
            staged_source = str(input_path)
            if kind=='ace-step':
                (directory/'inputs').mkdir()
                input_path.replace(directory/'inputs'/'source.wav')
                staged_source=[{'filename':'inputs/source.wav'}]
            encoded = json.dumps({**plan, 'source_audio': staged_source}, ensure_ascii=False, allow_nan=False).encode('utf-8')
        from .ai_torch_diagnostics import enabled as torch_diagnostics_enabled, read_report
        from .ai_gpu_verified import readiness as gpu_readiness, VERIFIED_KINDS
        from .ai_worker_registry import extensions
        verified_kind=kind in VERIFIED_KINDS or extensions().get(kind,{}).get('metering_method')=='gpu-kernel-union-v1'
        verified_enabled=verified_kind and gpu_readiness()['ready']
        if torch_diagnostics_enabled() or verified_enabled:
            # The server, never the request, assigns diagnostic identity.
            encoded = json.dumps({**json.loads(encoded), 'gpu_profile_task_id': job_id},
                                 ensure_ascii=False, allow_nan=False).encode('utf-8')
        request_path.write_bytes(encoded)
        request_path.chmod(0o600)
        from .ai_worker_registry import worker_python
        args = ([worker_python(kind), str(worker)] if worker.suffix == '.py' else [str(worker)])
        args += ['--request', str(request_path), '--output', str(output_path)]
        result = None
        gpu_slot_acquired = False
        observed_at = float('-inf')
        def diagnostic_checkpoint(*, final=False):
            nonlocal observed_at
            if final or time.monotonic() - observed_at >= 2:
                observed_at = time.monotonic()
                try:
                    from .ai_torch_diagnostics import store_report
                    report = read_report(directory, job_id)
                    if report:
                        store_report(job_id, report)
                    from .ai_compute_diagnostics import store as store_live_counters
                    counters = dict(report or {})
                    try:
                        raw_progress = json.loads((directory/'progress.json').read_text())
                    except (OSError, ValueError):
                        raw_progress = {}
                    if isinstance(raw_progress, dict):
                        counters = {**raw_progress, **counters}
                    store_live_counters(job_id, counters)
                    if queue_id and counters:
                        from .storage import _atomic_json_write
                        allowed={'phase','message','progress_percent','progress_source','progress_estimated','steps_completed','steps_total','cpu_seconds_estimated','gpu_seconds_estimated','gpu_metrics_status','gpu_metrics_source'}
                        published={k:v for k,v in counters.items() if k in allowed}
                        _atomic_json_write(queue._ROOT/(queue_id+'.progress.json'),published)
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).warning('GPU diagnostic update failed: %s', type(exc).__name__)
            return cancel_check() if not final and cancel_check is not None else False
        worker_cancel_check = diagnostic_checkpoint
        try:
            if gpu_slot_enabled:
                from . import ai_gpu_slot_accounting as gpu_slots
                gpu_slots.acquire(job_id, os.getenv('MTA_AI_GPU_LOGICAL_DEVICE', 'gpu0'))
                gpu_slot_acquired = True
            if os.getenv('MTA_AI_CGROUP_PARENT'):
                from .ai_cgroup_metering import run_cgroup_process
                result = run_cgroup_process(args, cwd=folder, timeout_seconds=timeout_seconds, cancel_check=worker_cancel_check, env={**os.environ,'MTA_AI_PROGRESS_FILE':str(directory/'progress.json'),'MTA_AI_SUPERVISOR_CPU_PROGRESS':'0' if kind=='ace-step' else '1','MTA_AI_VERIFIED_REPORT_DIR':str(directory),'MTA_AI_JOB_MAX_ARTIFACT_MIB':str(artifact_limit_mib)})
            else:
                result = run_metered_process(args, cwd=folder, timeout_seconds=timeout_seconds, cancel_check=worker_cancel_check, env={**os.environ,'MTA_AI_PROGRESS_FILE':str(directory/'progress.json'),'MTA_AI_SUPERVISOR_CPU_PROGRESS':'0' if kind=='ace-step' else '1','MTA_AI_VERIFIED_REPORT_DIR':str(directory),'MTA_AI_JOB_MAX_ARTIFACT_MIB':str(artifact_limit_mib)})
            if cancel_check is not None and cancel_check():
                raise RuntimeError('AI worker cancelled; result discarded')
            diagnostic_checkpoint(final=True)
            if result.exit_code:
                raise WorkerUnavailable('AI worker failed or timed out')
            payload, media_type = package_artifacts(directory, max_bytes=artifact_budget)
            # Packaging may be expensive for multi-stem adapters. A cancellation
            # during this phase must not finalize a successful billed job.
            if cancel_check is not None and cancel_check():
                raise RuntimeError("AI worker cancelled during artifact packaging")
            info = {"format": "wav" if media_type == "audio/wav" else "artifact-zip"}
            usage = {key: value for key, value in result.usage.items() if key not in ('disk_read_bytes', 'disk_write_bytes')}
            # Transient worker I/O is diagnostic only, never billable disk use.
            # The output may already be counted in /proc/<pid>/io. Never add
            # its size a second time as if it were extra physical disk I/O.
            if gpu_slot_acquired:
                gpu_slots.release(job_id)
                gpu_slot_acquired = False
            metered_source=result.source if result.isolated else 'unmetered'
            usage=usage if result.isolated else {}
            if verified_enabled:
                try:
                    from .ai_gpu_verified import consume_report
                    segments=(len(plan.get('singers',[])) if plan.get('selected','all')=='all' else 1) if kind=='singer-separation' else (None if kind=='ace-step' else 1)
                    usage['gpu_seconds']=consume_report(job_id,directory,ace=kind=='ace-step',expected_segments=segments)
                    metered_source='gpu-kernel-verified'
                except (OSError,ValueError,TypeError,KeyError):
                    pass  # Missing/incomplete evidence can never create a GPU charge.
            if not defer_settlement:ai_billing.finish_job(job_id, 'done', usage or None,source=metered_source)
            diagnostics = dict(result.gpu_diagnostics or {})
            profile_report = read_report(directory, job_id)
            if profile_report:
                diagnostics['torch_profile'] = profile_report
                diagnostic_checkpoint(final=True)
            return payload, {'job_id': job_id, 'audio': info, 'usage': usage,
                             'gpu_metered': 'gpu_seconds' in usage, 'metering_source':metered_source,'process_tree_metered': result.isolated,
                             'gpu_diagnostics': diagnostics, 'media_type': media_type}
        except BaseException:
            diagnostic_checkpoint(final=True)
            terminal_status='cancelled' if cancel_check is not None and cancel_check() else 'failed'
            if gpu_slot_acquired:
                # Do not silently finalize a job if its lease cannot be
                # accounted for. Recovery must reconcile it explicitly.
                gpu_slots.release(job_id, aborted=True)
                gpu_slot_acquired = False
            if result is None:
                ai_billing.finish_job(job_id, terminal_status, source='unmetered')
            else:
                ai_billing.finish_job(job_id, terminal_status, result.usage if result.isolated else None,
                                      source=result.source if result.isolated else 'unmetered')
            raise


def execute_registered_worker(user_id,kind,plan,*,token_id=None,timeout_seconds=1200,source_wav=None,cancel_check=None):
    from .ai_global_execution import execute
    return execute(user_id,kind,lambda cancelled:_execute_registered_worker(user_id,kind,plan,
        token_id=token_id,timeout_seconds=timeout_seconds,source_wav=source_wav,cancel_check=cancelled),cancel_check=cancel_check)
