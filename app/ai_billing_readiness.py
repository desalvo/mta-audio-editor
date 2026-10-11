"""Conservative readiness diagnostics for per-user AI billing.

Never substitute device-wide utilization for job-specific telemetry.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import ai_billing


def check() -> dict:
    rates = ai_billing.prices()
    issues: list[dict[str, str]] = []
    components: dict[str, dict] = {}

    def component(name: str, valid: bool, description: str):
        components[name] = {'ready': valid, 'description': description}
        if not valid:
            issues.append({'component': name, 'reason': description})

    root = os.getenv('MTA_AI_CGROUP_PARENT', '')
    valid_cgroup = False
    if sys.platform == 'linux' and root:
        try:
            path = Path(root).resolve(strict=True)
            valid_cgroup = (path.is_relative_to(Path('/sys/fs/cgroup'))
                            and path != Path('/sys/fs/cgroup')
                            and os.access(path, os.W_OK)
                            and {'cpu', 'io'} <= set((path / 'cgroup.controllers').read_text().split())
                            and {'cpu', 'io'} <= set((path / 'cgroup.subtree_control').read_text().split()))
        except (OSError, ValueError):
            pass
    component('cpu_process_tree', valid_cgroup,
              'A writable delegated cgroup v2 subtree with cpu and io controllers is required'
              if not valid_cgroup else 'Per-job cgroup CPU and I/O counters are available')

    try:
        from .ai_worker_protocol import configured_worker
        worker = configured_worker()
    except (OSError, ValueError):
        worker = None
    component('worker', worker is not None,
              'No trusted AI worker is configured' if worker is None else 'An operator-configured AI worker is available')

    # This application does NOT currently supply an attested per-job GPU sensor.
    # A configured key or a device-wide driver utility must never pass this check.
    gpu_paid = any(rates.get(key, 0) > 0 for key in ('gpu_seconds', 'gpu_energy_joules'))
    components['gpu_per_job'] = {
        'ready': False,
        'description': 'No validated per-job GPU time/energy sensor is integrated; host-wide GPU counters are forbidden',
        'paid_tariff_active': gpu_paid,
    }
    if gpu_paid:
        issues.append({'component': 'gpu_per_job', 'reason': components['gpu_per_job']['description']})

    disk_paid = rates.get('disk_gb_hours', 0) > 0
    storage_root = os.getenv('MTA_AI_USER_STORAGE_ROOT', '')
    root_ok = bool(storage_root and Path(storage_root).is_dir() and os.access(storage_root, os.R_OK))
    component('persistent_storage', not disk_paid or root_ok,
              ('Paid storage requires a readable per-user persistent storage root'
               if disk_paid and not root_ok else 'Persistent storage tariff disabled or directory configured'))
    return {'ready_for_paid_resources': not issues, 'components': components,
            'issues': issues, 'warning': 'Readiness is a preflight, not certification of GPU hardware or metering accuracy'}
