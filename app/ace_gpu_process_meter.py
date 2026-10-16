"""Best-effort ACE-Step process telemetry for MTA r210.

These are process-level deltas, NOT verified per-job usage or billing data.
Never convert wall-clock elapsed time into CPU or GPU time.
"""
from __future__ import annotations
import json
import math
import os
import re
import subprocess
from urllib.parse import urlsplit


def _number_ns(value):
    if isinstance(value, bool): return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) and value >= 0 else None
    if isinstance(value, str):
        m = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*ns\s*', value, re.I)
        return float(m.group(1)) if m else None
    return None


def gfx_ns_for_pid(document, pid):
    """Match AMD-SMI process JSON objects and their USAGE.GFX nanosecond counters.

    Never accept an unrelated GPU's global usage percentage as job usage.
    """
    matches = []
    def walk(value):
        if isinstance(value, list):
            for v in value: walk(v)
        elif isinstance(value, dict):
            candidate = value.get('PID', value.get('pid'))
            try: matching = candidate is not None and int(candidate) == int(pid)
            except (TypeError, ValueError): matching = False
            if matching:
                usage = value.get('USAGE', value.get('usage'))
                if isinstance(usage, dict):
                    ns = _number_ns(usage.get('GFX', usage.get('gfx')))
                    if ns is not None: matches.append(ns)
            for v in value.values(): walk(v)
    walk(document)
    # One process may appear under several GPU records. Sum engine nanoseconds.
    return sum(matches) if matches else None


def _ace_pid():
    configured = os.environ.get('MTA_ACE_STEP_GPU_METRICS_PID', '').strip()
    if configured:
        return int(configured) if configured.isdecimal() and int(configured) > 0 else None
    try:
        result = subprocess.run(['systemctl','show','-p','MainPID','--value','mta-ace-step.service'],
                                capture_output=True,text=True,timeout=2,check=True)
        pid = int(result.stdout.strip())
        return pid if pid > 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _cpu_seconds(pid):
    """Linux process utime+stime; no wall-clock conversion."""
    try:
        s = open(f'/proc/{pid}/stat', encoding='utf-8').read()
        fields = s[s.rfind(')')+2:].split()
        # stat fields start at #3 after comm; utime #14, stime #15.
        return (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')
    except (OSError, ValueError, IndexError):
        return None


class AceProcessMeter:
    def __init__(self, endpoint):
        self.pid = _ace_pid() if urlsplit(endpoint).hostname in ('127.0.0.1','localhost','::1') else None
        self.baseline_gpu = None
        self.baseline_cpu = None
        self.last_gpu = None
        self.last_cpu = None
        self.samples = 0
        self._valid = False

    def sample(self):
        if not self.pid: return {}
        try:
            result = subprocess.run(['amd-smi','process','--pid',str(self.pid),'--json'],
                                    capture_output=True,text=True,timeout=4,check=True)
            counter = gfx_ns_for_pid(json.loads(result.stdout), self.pid)
        except (OSError, ValueError, subprocess.SubprocessError):
            counter = None
        cpu = _cpu_seconds(self.pid)
        if counter is not None:
            if self.baseline_gpu is None: self.baseline_gpu = counter
            elif counter >= self.baseline_gpu:
                self.last_gpu = (counter - self.baseline_gpu) / 1e9
            else: self.baseline_gpu = counter; self.last_gpu = None
        if cpu is not None:
            if self.baseline_cpu is None: self.baseline_cpu = cpu
            elif cpu >= self.baseline_cpu:
                self.last_cpu = cpu - self.baseline_cpu
            else: self.baseline_cpu = cpu; self.last_cpu = None
        self.samples += 1
        data = {}
        if self.last_gpu is not None: data['gpu_seconds_estimated'] = round(self.last_gpu, 3)
        if self.last_cpu is not None: data['cpu_seconds_estimated'] = round(self.last_cpu, 3)
        return data
