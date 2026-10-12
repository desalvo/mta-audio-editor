"""Fail-closed AMD SMI snapshot and host/LXC PID correlation (diagnostics only).

AMD SMI may expose host PIDs not visible inside a Proxmox LXC. Never
silently equate host and container PIDs. An agent with host /proc access
must independently verify every mapped process against its job cgroup.
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path


class GPUAttributionError(ValueError):
    """Invalid or incomplete GPU telemetry; never produce billable data."""


def _gpu_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GPUAttributionError('Invalid GPU index')
    return value


def _pid(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise GPUAttributionError('Invalid host PID')
    return value


def _value(section: object) -> float | None:
    if not isinstance(section, dict):
        return None
    number = section.get('value')
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        return None
    number = float(number)
    return number if math.isfinite(number) and number >= 0 else None


def parse_process_json(payload: str | list, *, gpu_index: int = 0) -> dict:
    """Normalize `amd-smi process --gpu N --json` output, not its text table."""
    gpu_index = _gpu_id(gpu_index)
    try:
        documents = json.loads(payload) if isinstance(payload, str) else payload
    except (ValueError, TypeError) as exc:
        raise GPUAttributionError('AMD SMI did not return valid JSON') from exc
    if not isinstance(documents, list):
        raise GPUAttributionError('Unexpected AMD SMI process structure')
    matches = [entry for entry in documents if isinstance(entry, dict)
               and entry.get('gpu') == gpu_index]
    if len(matches) != 1 or not isinstance(matches[0].get('process_list'), list):
        raise GPUAttributionError('GPU process list missing or ambiguous')
    processes = {}
    for record in matches[0]['process_list']:
        if not isinstance(record, dict) or not isinstance(record.get('process_info'), dict):
            raise GPUAttributionError('Invalid GPU process record')
        info = record['process_info']
        pid = _pid(info.get('pid'))
        if pid in processes:
            raise GPUAttributionError('Duplicate host PID')
        usage = info.get('usage')
        gfx = _value(usage.get('gfx')) if isinstance(usage, dict) else None
        memory = _value(info.get('mem_usage'))
        processes[pid] = {'host_pid': pid, 'gfx_ns': gfx,
                          'memory_bytes': memory, 'gpu_index': gpu_index}
    return {'gpu_index': gpu_index, 'processes': processes,
            'source': 'amd-smi-process-json', 'billing_eligible': False}


def collect_process_snapshot(*, gpu_index: int = 0, executable: str = 'amd-smi',
                             timeout_seconds: float = 8.0) -> dict:
    """Read-only CLI call; no shell expansion or privilege escalation."""
    gpu_index = _gpu_id(gpu_index)
    if not (0 < timeout_seconds <= 60):
        raise GPUAttributionError('Invalid AMD SMI timeout')
    try:
        result = subprocess.run([executable, 'process', '--gpu', str(gpu_index), '--json'],
                                capture_output=True, text=True, timeout=timeout_seconds,
                                check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise GPUAttributionError('AMD SMI process collection failed') from exc
    return parse_process_json(result.stdout, gpu_index=gpu_index)


def _read_host_cgroup(pid: int, *, proc_root: Path) -> str | None:
    """Only a host-view /proc can certify the process-to-job mapping."""
    try:
        rows = (proc_root / str(pid) / 'cgroup').read_text().splitlines()
    except (OSError, UnicodeError):
        return None
    paths = [line.split(':', 2)[2] for line in rows if line.startswith('0::')
             and len(line.split(':', 2)) == 3]
    return paths[0] if len(paths) == 1 else None


def correlate_processes(snapshot: dict, *, job_cgroups: dict[str, str],
                        proc_root: Path = Path('/proc'),
                        host_pid_namespace_verified: bool = False) -> dict:
    """Map AMD SMI host PIDs only using host-verified cgroup identities.

    If running inside LXC, the caller MUST leave host_pid_namespace_verified
    False. Unknown/external PIDs invalidate a shared-capacity attribution
    window rather than charging their work to MTA.
    """
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get('processes'), dict):
        raise GPUAttributionError('Invalid GPU snapshot')
    if not isinstance(job_cgroups, dict) or len(job_cgroups) > 10000:
        raise GPUAttributionError('Invalid job cgroup registry')
    paths = {}
    for job_id, group in job_cgroups.items():
        if (not isinstance(job_id, str) or not job_id or len(job_id) > 128
                or not isinstance(group, str) or not group.startswith('/')
                or group == '/' or '..' in group.split('/')):
            raise GPUAttributionError('Invalid job cgroup identity')
        if group.rstrip('/') in paths:
            raise GPUAttributionError('Duplicate cgroup assignment')
        paths[group.rstrip('/')] = job_id
    matches = {}
    unknown = []
    for raw_pid in snapshot['processes']:
        pid = _pid(raw_pid)
        # Do not trust container /proc for an AMD SMI host PID.
        group = (_read_host_cgroup(pid, proc_root=proc_root)
                 if host_pid_namespace_verified else None)
        job = None
        if group is not None:
            candidates = [job_id for prefix, job_id in paths.items()
                          if group == prefix or group.startswith(prefix + '/')]
            if len(candidates) == 1:
                job = candidates[0]
        if job is None:
            unknown.append(pid)
        else:
            matches[pid] = job
    return {'gpu_index': snapshot.get('gpu_index'), 'host_pid_to_job': matches,
            'unknown_host_pids': sorted(unknown),
            'external_or_unverified_activity': bool(unknown),
            'attribution_verified': bool(host_pid_namespace_verified and not unknown),
            'billing_eligible': False, 'source': 'amd-smi-host-cgroup-v1'}


def diagnostic_window(*, start: float, end: float, utilization: float | None,
                      job_weights: dict[str, float], correlation: dict) -> dict:
    """Feed the shared estimator; never infer global utilization from per-PID VRAM."""
    if not isinstance(correlation, dict):
        raise GPUAttributionError('Missing correlation')
    return {'start': start, 'end': end, 'utilization': utilization,
            'jobs': job_weights,
            'external_activity': not correlation.get('attribution_verified', False)}
