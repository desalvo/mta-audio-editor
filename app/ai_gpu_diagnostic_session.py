"""Read-only multi-snapshot GPU attribution diagnostics; never billable."""
from __future__ import annotations

import json
import math
import os
import tempfile
import time
from pathlib import Path

from .ai_amd_smi_collector import GPUAttributionError
from .ai_gpu_attribution_report import collect_attribution_report


def collect_session(*, job_cgroups: dict[str, str], samples: int = 3,
                    interval_seconds: float = 0.25, gpu_index: int = 0,
                    proc_root: Path = Path('/proc'),
                    host_pid_namespace_verified: bool = False,
                    executable: str = 'amd-smi', sleep=time.sleep,
                    clock=time.monotonic) -> dict:
    """Collect bounded host-verified snapshots, preserving every uncertainty.

    A snapshot is not a billable GPU clock. No inference or accounting is run.
    """
    if isinstance(samples, bool) or not isinstance(samples, int) or not 1 <= samples <= 100:
        raise GPUAttributionError('Invalid sample count')
    if (isinstance(interval_seconds, bool) or not isinstance(interval_seconds, (int, float))
            or not math.isfinite(interval_seconds) or not 0 <= interval_seconds <= 60):
        raise GPUAttributionError('Invalid sample interval')
    if not host_pid_namespace_verified:
        raise GPUAttributionError('Host PID namespace identity has not been verified')
    records = []
    for index in range(samples):
        if index:
            sleep(interval_seconds)
        tick = clock()
        report = collect_attribution_report(job_cgroups=job_cgroups, gpu_index=gpu_index,
            proc_root=proc_root, host_pid_namespace_verified=True, executable=executable)
        records.append({'index': index, 'monotonic_seconds': tick, 'report': report})
    jobs = sorted({row['job_id'] for entry in records
                   for row in entry['report']['processes'] if row['job_id'] is not None})
    external = any(entry['report']['external_activity_detected'] for entry in records)
    fully_attributed = all(entry['report']['attribution_verified'] for entry in records)
    return {'schema': 'mta-gpu-diagnostic-session-v1', 'gpu_index': gpu_index,
            'sample_count': len(records), 'samples': records, 'observed_jobs': jobs,
            'external_activity_detected': external, 'attribution_verified_in_all_samples': fully_attributed,
            'billing_eligible': False, 'measured_gpu_seconds': None,
            'warning': 'Diagnostic sampling only; not a GPU utilization or billing meter.'}


def write_session_report(destination: Path, report: dict) -> None:
    """Atomically persist diagnostics, rejecting any pretend-billable report."""
    if (not isinstance(report, dict) or report.get('schema') != 'mta-gpu-diagnostic-session-v1'
            or report.get('billing_eligible') is not False
            or report.get('measured_gpu_seconds') is not None):
        raise GPUAttributionError('Invalid or billable diagnostic report')
    destination = Path(destination)
    payload = (json.dumps(report, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode()
    if len(payload) > 10_000_000:
        raise GPUAttributionError('Diagnostic report too large')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.mta-gpu-',
                                         suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
