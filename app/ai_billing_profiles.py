"""Illustrative hardware-aware electricity-cost rates, never automatic charges.

Rates are integer micro-EUR per unit. APU CPU/GPU allocations are independent
accounting assumptions, NOT independently measured chip power.
"""
from __future__ import annotations

import os
import platform
import re
import subprocess

ELECTRICITY_EUR_PER_KWH = 0.4343  # ARERA Q4 2026 household benchmark incl. tax
MODEL_VERSION = 'it-electricity-2026q4-v1'
# Electricity equivalent: 1 microEUR/s = 8.289W at 0.4343 EUR/kWh.
GPU_PROFILES = {
    'AMD Radeon 8060S': {'micro_per_unit': 10, 'assumed_watts': 82.89},
    'AMD Radeon 8050S': {'micro_per_unit': 8, 'assumed_watts': 66.31},
    'AMD Radeon 780M': {'micro_per_unit': 4, 'assumed_watts': 33.15},
}
CPU_PROFILES = {
    'AMD Ryzen AI MAX+ 395': {'micro_per_unit': 1, 'assumed_watts_per_core': 8.289},
    'AMD Ryzen AI MAX 390': {'micro_per_unit': 1, 'assumed_watts_per_core': 8.289},
    'AMD Ryzen 9 7940HS': {'micro_per_unit': 1, 'assumed_watts_per_core': 8.289},
}
DISK_RATE = 2  # microEUR / GiB-hour; generic persistent-capacity proxy


def canonical_gpu(name: str) -> str | None:
    if not isinstance(name, str):
        return None
    for model in GPU_PROFILES:
        if model.casefold() in name.casefold():
            return model
    return None


def canonical_cpu(name: str) -> str | None:
    if not isinstance(name, str):
        return None
    value = re.sub(r'\s+', ' ', name).casefold()
    for model in CPU_PROFILES:
        if model.casefold() in value:
            return model
    return None


def local_cpu_model() -> str:
    override = os.getenv('MTA_AI_CPU_MODEL', '').strip()
    if override:
        return override
    try:
        with open('/proc/cpuinfo', encoding='utf-8') as handle:
            for line in handle:
                if line.lower().startswith('model name'):
                    return line.partition(':')[2].strip()
    except OSError:
        pass
    return platform.processor() or 'unknown'



def local_gpu_model() -> str:
    """Detect a GPU without assuming PCI identity or requiring an LXC host agent.

    Discovery is advisory: never applies prices to jobs or enables billing.
    Explicit overrides are useful for remote workers but cannot prove their hardware.
    """
    override = os.getenv('MTA_AI_GPU_MODEL', '').strip()
    if override:
        return override
    try:
        result = subprocess.run(
            ['rocminfo'], capture_output=True, text=True, timeout=5, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return 'unknown'
    if len(result.stdout) > 1_000_000:
        return 'unknown'
    # rocminfo lists CPU agents too. Require a GPU agent block for the match.
    blocks = re.split(r'(?=^\s*Agent \d+\s*$)', result.stdout, flags=re.MULTILINE)
    matches = set()
    for block in blocks:
        if not re.search(r'^\s*Device Type:\s*GPU\s*$', block, re.MULTILINE):
            continue
        for name in re.findall(r'^\s*Marketing Name:\s*(.*?)\s*$', block, re.MULTILINE):
            model = canonical_gpu(name)
            if model:
                matches.add(model)
    return next(iter(matches)) if len(matches) == 1 else 'unknown'

def suggested_prices(*, cpu_model: str | None = None, gpu_model: str | None = None) -> dict:
    cpu = canonical_cpu(local_cpu_model() if cpu_model is None else cpu_model)
    gpu = canonical_gpu(local_gpu_model() if gpu_model is None else gpu_model)
    return {
        'model_version': MODEL_VERSION,
        'electricity_eur_per_kwh': ELECTRICITY_EUR_PER_KWH,
        'cpu_model': cpu,
        'gpu_model': gpu,
        'suggested_micro_per_unit': {
            'cpu_seconds': CPU_PROFILES[cpu]['micro_per_unit'] if cpu else None,
            'gpu_slot_seconds_estimated': GPU_PROFILES[gpu]['micro_per_unit'] if gpu else None,
            'disk_gb_hours': DISK_RATE,
        },
        'units': {'cpu_seconds': 'CPU core-second (cgroup CPU time)',
                  'gpu_slot_seconds_estimated': 'equivalent allocated GPU-slot-second',
                  'disk_gb_hours': 'GiB-hour of persistent capacity'},
        'billing_enabled_by_default': False,
        'note': 'Illustrative electricity-based cost assumptions only; CPU/GPU APU power overlaps, no external GPU jobs observed.',
    }
