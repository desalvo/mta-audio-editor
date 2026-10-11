"""Per-process Linux DRM GPU telemetry: diagnostic, never host-wide billing.

DRM fdinfo engines are reported per file descriptor and driver, in ns; this
collector never reads card-wide busy/load/power counters. Sampling can miss a
process that exits between polls, so values are *not* certified for invoicing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ENGINE = re.compile(r'^drm-engine-([a-zA-Z0-9_-]+):\s*(\d+)\s*ns\s*$')
_GPU_ENGINES = ('render', 'compute', 'gfx', '3d', 'dma', 'copy', 'video', 'vcn')


def pid_engine_ns(pid: int, *, proc_root: Path = Path('/proc')) -> dict[str, int]:
    """Return maximum observed DRM engine runtime per engine, for one PID.

    Multiple duplicated descriptors can refer to the same DRM client, so do
    not sum their reported runtimes. When fdinfo exposes drm-client-id,
    group descriptors by client ID before summing *distinct* clients.
    """
    fd_root = proc_root / str(pid) / 'fdinfo'
    clients: dict[tuple[str, str], dict[str, int]] = {}
    for entry in fd_root.iterdir():
        try:
            contents = entry.read_text()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        driver = next((line.split(':', 1)[1].strip() for line in contents.splitlines()
                       if line.startswith('drm-driver:')), None)
        client_id = next((line.split(':', 1)[1].strip() for line in contents.splitlines()
                          if line.startswith('drm-client-id:')), None)
        if not driver or client_id is None:
            continue
        # A given DRM client may have several duplicate fds; use max by engine.
        values = clients.setdefault((driver, client_id), {})
        for line in contents.splitlines():
            match = _ENGINE.fullmatch(line.strip())
            if match:
                engine, count = match.group(1), int(match.group(2))
                if engine.lower().startswith(_GPU_ENGINES):
                    values[engine] = max(values.get(engine, 0), count)
    merged: dict[str, int] = {}
    for values in clients.values():
        for engine, count in values.items():
            merged[engine] = merged.get(engine, 0) + count
    return merged


def cgroup_gpu_snapshot(cgroup: Path, *, proc_root: Path = Path('/proc')) -> dict[int, dict[str, int]]:
    """Inspect only PIDs *inside* the designated job cgroup hierarchy."""
    snapshot: dict[int, dict[str, int]] = {}
    for group in (cgroup, *cgroup.rglob('cgroup.procs')):
        process_file = group if group.name == 'cgroup.procs' else group / 'cgroup.procs'
        for value in process_file.read_text().split():
            pid = int(value)
            try:
                snapshot[pid] = pid_engine_ns(pid, proc_root=proc_root)
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                # Cannot certify a full lifetime if a process disappears here.
                raise RuntimeError('GPU process exited during telemetry collection') from None
    return snapshot


_MEMORY = re.compile(r'^drm-(memory|resident|shared|active|purgeable)-([a-zA-Z0-9_-]+):\s*(\d+)\s*(?:KiB|kB)\s*$')


@dataclass(frozen=True)
class DRMProcessSample:
    """Actual per-client counters, not an energy or hardware utilization estimate.

    Engine counters count execution time on an engine, and multiple engines
    may run in parallel. Memory figures are KiB gauges, not accumulated use.
    Neither is a certificate of lifetime consumption when the process exits.
    """
    engine_ns: dict[str, int]
    memory_kib: dict[str, int]


def pid_gpu_sample(pid: int, *, proc_root: Path = Path('/proc')) -> DRMProcessSample:
    """Read only the target PID's DRM fdinfo; deduplicate client descriptors.

    On DRM implementations that omit drm-client-id the sample is incomplete,
    never inferred from the GPU device's total utilization counters.
    """
    directory = proc_root / str(pid) / 'fdinfo'
    clients: dict[tuple[str, str], dict[str, dict[str, int]]] = {}
    for entry in directory.iterdir():
        try:
            lines = entry.read_text().splitlines()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        properties = dict(line.split(':', 1) for line in lines if ':' in line)
        driver = properties.get('drm-driver', '').strip()
        client_id = properties.get('drm-client-id', '').strip()
        if not driver or not client_id:
            continue
        counts = clients.setdefault((driver, client_id), {'engines': {}, 'memory': {}})
        for line in lines:
            engine = _ENGINE.fullmatch(line.strip())
            if engine and engine.group(1).lower().startswith(_GPU_ENGINES):
                name, ns = engine.group(1), int(engine.group(2))
                counts['engines'][name] = max(counts['engines'].get(name, 0), ns)
            memory = _MEMORY.fullmatch(line.strip())
            if memory:
                field, region, kib = memory.groups()
                # The 'memory' field describes allocations; 'resident' memory
                # describes GPU residency. Do not add the two categories.
                name = f'{field}-{region}'
                counts['memory'][name] = max(counts['memory'].get(name, 0), int(kib))
    engines: dict[str, int] = {}
    memory: dict[str, int] = {}
    for counts in clients.values():
        for key, value in counts['engines'].items():
            engines[key] = engines.get(key, 0) + value
        for key, value in counts['memory'].items():
            memory[key] = memory.get(key, 0) + value
    return DRMProcessSample(engines, memory)


def cgroup_gpu_detailed_snapshot(cgroup: Path, *, proc_root: Path = Path('/proc')) -> dict[int, DRMProcessSample]:
    """Collect per-PID GPU counters only from the designated job subtree."""
    snapshot: dict[int, DRMProcessSample] = {}
    for entry in (cgroup / 'cgroup.procs', *cgroup.rglob('cgroup.procs')):
        for value in entry.read_text().split():
            pid = int(value)
            try:
                snapshot[pid] = pid_gpu_sample(pid, proc_root=proc_root)
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                raise RuntimeError('GPU process exited during telemetry collection') from None
    return snapshot
