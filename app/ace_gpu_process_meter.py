"""Sample ACE service process counters; diagnostic estimates, never billing."""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

GPU_STATUSES = frozenset(('remote_endpoint', 'pid_unavailable', 'process_unreadable',
    'process_changed', 'baseline_only', 'sampled_process', 'amd_smi_missing',
    'amd_smi_failed', 'amd_smi_timeout', 'amd_smi_invalid_json',
    'counter_unavailable', 'counter_reset', 'zero_counter_unverified',
    'host_agent_not_configured', 'host_agent_auth_unavailable', 'host_agent_unavailable',
    'host_agent_mapping_unavailable', 'host_agent_counter_unavailable',
    'host_agent_socket_missing', 'host_agent_socket_missing_in_mount', 'host_agent_socket_access_denied'))
GPU_SOURCES = frozenset(('none', 'amd-smi-process', 'drm-fdinfo', 'proxmox-host-drm', 'proxmox-host-amd-smi'))


def _number_ns(value):
    if isinstance(value, bool): return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) and value >= 0 else None
    if isinstance(value, str):
        m = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*ns\s*', value, re.I)
        return float(m.group(1)) if m else None
    return None


def gfx_ns_for_pid(document, pid):
    """Accept only process GFX ns, never device-wide percentages."""
    matches = []
    def walk(value):
        if isinstance(value, list):
            for v in value: walk(v)
        elif isinstance(value, dict):
            candidate = value.get('PID', value.get('pid'))
            try: matching = candidate is not None and not isinstance(candidate, bool) and int(candidate) == int(pid)
            except (TypeError, ValueError, OverflowError): matching = False
            if matching:
                usage = value.get('USAGE', value.get('usage'))
                if isinstance(usage, dict):
                    ns = _number_ns(usage.get('GFX', usage.get('gfx')))
                    if ns is not None: matches.append(ns)
            for v in value.values(): walk(v)
    walk(document)
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


def _process_identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return fields[19]  # Linux starttime field 22; rejects PID reuse.
    except (OSError, ValueError, IndexError):
        return None


def _cpu_seconds(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')
    except (OSError, ValueError, IndexError):
        return None


def _drm_counter(pid):
    # The installed file also runs outside the app package (trusted sibling path).
    try:
        if __package__:
            from .ai_gpu_process_meter import pid_engine_ns
        else:
            from ai_gpu_process_meter import pid_engine_ns
        engines = pid_engine_ns(pid)
        return sum(engines.values()) if engines else None
    except (ImportError, OSError, ValueError):
        return None



def execution_environment():
    if os.environ.get('container', '').strip().lower() == 'lxc': return 'lxc'
    for path in ('/run/systemd/container', '/proc/self/cgroup'):
        try:
            text = Path(path).read_text()[:8192]
            if text.strip() == 'lxc' or re.search(r'/(?:lxc/|lxc\.payload\.)', text): return 'lxc'
        except OSError:
            pass
    return 'other'


def _agent_requested(environment):
    return environment == 'lxc' or bool(os.getenv('MTA_AI_GPU_HOST_AGENT_SOCKET')) or any(
        os.path.exists(p) for p in ('/opt/mta-gpu-agent-host/agent.sock', '/run/mta-gpu-agent/agent.sock'))


def _host_agent_counter(pid, identity):
    """Match namespace inode, inner PID AND process start time; never guess PIDs."""
    try:
        if __package__:
            from .ai_proxmox_gpu_agent_client import snapshot
        else:
            from ai_proxmox_gpu_agent_client import snapshot
        response = snapshot()
        if response.get('available') is not True:
            reason = response.get('reason')
            return None, 'none', {'not-configured':'host_agent_not_configured',
                'agent-token-not-configured':'host_agent_auth_unavailable',
                'agent-socket-missing':'host_agent_socket_missing',
                'agent-socket-missing-in-mount':'host_agent_socket_missing_in_mount',
                'agent-socket-access-denied':'host_agent_socket_access_denied'}.get(reason, 'host_agent_unavailable')
        telemetry = response['telemetry']
        if telemetry.get('source') != 'host-amd-smi': return None, 'none', 'host_agent_unavailable'
        inode = Path(f'/proc/{pid}/ns/pid').stat().st_ino
        rows = [r for r in telemetry['processes'] if r.get('namespace_pid') == pid
                and r.get('pid_namespace_inode') == inode and r.get('process_start_ticks') == identity]
        if not rows or len({r['host_pid'] for r in rows}) != 1:
            return None, 'none', 'host_agent_mapping_unavailable'
        drm = [r['drm_engine_ns'] for r in rows if 'drm_engine_ns' in r]
        if drm and max(drm) > 0: return max(drm), 'proxmox-host-drm', 'baseline_only'
        gfx = [r['gfx_ns'] for r in rows if 'gfx_ns' in r]
        if gfx: return sum(gfx), 'proxmox-host-amd-smi', 'baseline_only'
        if drm: return max(drm), 'proxmox-host-drm', 'baseline_only'
        return None, 'none', 'host_agent_counter_unavailable'
    except (ImportError, OSError, ValueError, KeyError, TypeError):
        return None, 'none', 'host_agent_unavailable'


class AceProcessMeter:
    def __init__(self, endpoint):
        self.local = urlsplit(endpoint).hostname in ('127.0.0.1','localhost','::1')
        self.pid = _ace_pid() if self.local else None
        self.identity = _process_identity(self.pid) if self.pid else None
        self.environment = execution_environment()
        self.use_agent = _agent_requested(self.environment)
        self.baseline_gpu = self.baseline_cpu = None
        self.last_gpu = self.last_cpu = None
        self.source = 'none'
        self.previous_gpu = None

    def sample(self):
        data = {'gpu_metrics_source': 'none', 'gpu_metrics_status':
                'pid_unavailable' if self.local else 'remote_endpoint'}
        if not self.pid: return data
        before = _process_identity(self.pid)
        if self.identity is None or before is None:
            data['gpu_metrics_status'] = 'process_unreadable'
            return data
        if before != self.identity:
            data['gpu_metrics_status'] = 'process_changed'
            return data
        counter, source, reason = None, 'none', 'counter_unavailable'
        if self.use_agent:
            counter, source, reason = _host_agent_counter(self.pid, self.identity)
        if counter is None or counter == 0:
            drm = _drm_counter(self.pid)
            if drm is not None and (drm > 0 or counter is None):
                counter, source = drm, 'drm-fdinfo'
        # In LXC the AMD-SMI PID namespace/counters were already found unreliable.
        # Use the authenticated host agent or process DRM; do not retry local SMI.
        if (counter is None or counter == 0) and self.environment != 'lxc' and not self.use_agent:
            try:
                result = subprocess.run(['amd-smi','process','--pid',str(self.pid),'--json'],
                                        capture_output=True,text=True,timeout=4,check=True)
                smi = gfx_ns_for_pid(json.loads(result.stdout), self.pid)
                if smi is not None and (smi > 0 or counter is None):
                    counter, source = smi, 'amd-smi-process'
            except FileNotFoundError: reason = 'amd_smi_missing'
            except subprocess.TimeoutExpired: reason = 'amd_smi_timeout'
            except (OSError, subprocess.SubprocessError): reason = 'amd_smi_failed'
            except ValueError: reason = 'amd_smi_invalid_json'
        cpu = _cpu_seconds(self.pid)
        if _process_identity(self.pid) != self.identity:
            data['gpu_metrics_status'] = 'process_changed'
            return data
        self.last_gpu = self.last_cpu = None
        if counter is None:
            status = reason
        else:
            data['gpu_metrics_source'] = source
            if self.source != source or self.baseline_gpu is None:
                self.baseline_gpu, self.source = counter, source
                status = 'baseline_only'
            elif self.previous_gpu is not None and counter < self.previous_gpu:
                self.baseline_gpu = counter
                status = 'counter_reset'
            elif counter == self.baseline_gpu == 0:
                status = 'zero_counter_unverified'
            else:
                self.last_gpu = (counter - self.baseline_gpu) / 1e9
                status = 'sampled_process'
        if counter is not None: self.previous_gpu = counter
        if cpu is not None:
            if self.baseline_cpu is None or cpu < self.baseline_cpu: self.baseline_cpu = cpu
            else: self.last_cpu = cpu - self.baseline_cpu
        data['gpu_metrics_status'] = status
        if self.last_gpu is not None: data['gpu_seconds_estimated'] = round(self.last_gpu, 3)
        if self.last_cpu is not None: data['cpu_seconds_estimated'] = round(self.last_cpu, 3)
        return data
