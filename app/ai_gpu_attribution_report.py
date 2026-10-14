"""Read-only GPU process attribution report for trusted host agents.

This is diagnostic evidence, never an invoice or a hardware utilization meter.
Host PID namespace verification must be asserted by the operator on the host.
"""
from __future__ import annotations

import json
from pathlib import Path
from .ai_amd_smi_collector import (GPUAttributionError, collect_process_snapshot,
                                   correlate_processes)


def collect_attribution_report(*, job_cgroups: dict[str, str], gpu_index: int = 0,
                               proc_root: Path = Path('/proc'),
                               host_pid_namespace_verified: bool = False,
                               executable: str = 'amd-smi') -> dict:
    """Collect, correlate and classify one GPU snapshot without authorizing billing."""
    if not host_pid_namespace_verified:
        raise GPUAttributionError('Host PID namespace identity has not been verified')
    snapshot = collect_process_snapshot(gpu_index=gpu_index, executable=executable)
    correlation = correlate_processes(snapshot, job_cgroups=job_cgroups,
                                      proc_root=proc_root,
                                      host_pid_namespace_verified=True)
    rows = []
    for pid, info in sorted(snapshot['processes'].items()):
        rows.append({'host_pid': pid,
                     'job_id': correlation['host_pid_to_job'].get(pid),
                     'gpu_index': snapshot['gpu_index'],
                     'gfx_ns_reported': info['gfx_ns'],
                     'memory_bytes_reported': info['memory_bytes']})
    return {'schema': 'mta-gpu-attribution-diagnostic-v1',
            'source': snapshot['source'],
            'gpu_index': snapshot['gpu_index'],
            'processes': rows,
            'unmatched_pids': correlation['unknown_host_pids'],
            'attribution_verified': correlation['attribution_verified'],
            'external_activity_detected': correlation['external_or_unverified_activity'],
            'billing_eligible': False,
            'measured_gpu_seconds': None,
            'warning': 'Process correlation is diagnostic only; do not bill GPU utilization.'}


def report_json(**kwargs) -> str:
    """Deterministic, machine-readable report without credentials or audio data."""
    return json.dumps(collect_attribution_report(**kwargs), sort_keys=True,
                      ensure_ascii=False, separators=(',', ':'))
