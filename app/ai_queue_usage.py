"""Read-only queue resource view over authenticated worker accounting.

This projection never settles billing, invents idle GPU time or promotes live
samples/profiler diagnostics to verified ledger consumption.
"""
import json
import math
import sqlite3
from pathlib import Path
from contextlib import closing

TRUSTED_CPU = frozenset(('worker', 'cgroup', 'remote-worker', 'gpu-agent', 'gpu-kernel-verified'))


def number(value):
    return float(value) if type(value) in (int, float) and math.isfinite(value) and 0 <= value < 1e18 else None


def enrich(value):
    from .auth import db_path
    owner, job_id = value.get('actor_user_id'), value.get('job_id')
    if not isinstance(job_id, str):
        return value
    path = db_path()
    if not path.is_file():
        return value
    result = dict(value)
    try:
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=.2)) as con:
            con.row_factory = sqlite3.Row
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if type(owner) is not int or owner <= 0:
                if 'ai_compute_jobs' not in tables:
                    return value
                owners = con.execute('SELECT DISTINCT user_id FROM ai_compute_jobs WHERE queue_job_id=?', (job_id,)).fetchall()
                if len(owners) != 1 or type(owners[0][0]) is not int or owners[0][0] <= 0:
                    return value
                owner = owners[0][0]
                result['actor_user_id'] = owner
            if 'users' in tables:
                user = con.execute('SELECT username,display_name FROM users WHERE id=?', (owner,)).fetchone()
                if user:
                    result.update(actor_username=user['username'], actor_display_name=user['display_name'])
            if 'ai_compute_jobs' not in tables:
                return result
            rows = con.execute('SELECT id,status,usage_json,resource_source FROM ai_compute_jobs WHERE queue_job_id=? AND user_id=?', (job_id, owner)).fetchall()
            if not rows:
                return result
            diagnostics = {}
            if 'ai_compute_job_diagnostics' in tables:
                diagnostics = {r['job_id']: r['payload'] for r in con.execute('''SELECT d.job_id,d.payload FROM ai_compute_job_diagnostics d
                  JOIN ai_compute_jobs j ON j.id=d.job_id WHERE j.queue_job_id=? AND j.user_id=?''', (job_id, owner))}
            cpu = gpu = cpu_partial = gpu_partial = 0.0
            all_cpu = all_gpu = True
            have_cpu = have_gpu = False
            for row in rows:
                try:
                    usage = json.loads(row['usage_json'] or '{}')
                    diag = json.loads(diagnostics.get(row['id'], '{}'))
                    if not isinstance(usage, dict) or not isinstance(diag, dict):
                        raise ValueError('Invalid resource record')
                except (ValueError, TypeError):
                    usage, diag = {}, {}
                if row['resource_source']=='diagnostic-estimate':
                    for metric in ('cpu_seconds','gpu_seconds'):
                        if metric in usage:diag[metric+'_estimated']=usage[metric]
                    result['diagnostic_estimates_trusted']=True
                    result['gpu_metrics_source']='diagnostic-estimate'
                    result['gpu_metrics_status']='diagnostic_estimate_trusted'
                c = number(usage.get('cpu_seconds')) if row['status'] in ('done', 'failed', 'cancelled') and row['resource_source'] in TRUSTED_CPU else None
                g = number(usage.get('gpu_seconds')) if row['status'] in ('done', 'failed', 'cancelled') and row['resource_source'] in ('gpu-agent', 'gpu-kernel-verified') else None
                if g is not None and row['resource_source'] == 'gpu-kernel-verified':
                    evidence = con.execute('SELECT seconds FROM ai_verified_gpu_evidence WHERE job_id=?', (row['id'],)).fetchone() if 'ai_verified_gpu_evidence' in tables else None
                    if evidence is None or number(evidence[0]) != g:
                        g = None
                all_cpu &= c is not None
                all_gpu &= g is not None
                ce, ge = number(diag.get('cpu_seconds_estimated')), number(diag.get('gpu_seconds_estimated'))
                have_cpu |= c is not None or ce is not None
                have_gpu |= g is not None or ge is not None
                cpu += c or 0
                gpu += g or 0
                cpu_partial += c if c is not None else ce or 0
                gpu_partial += g if g is not None else ge or 0
            if result.get('cpu_seconds') is None:
                if all_cpu:
                    result['cpu_seconds'] = cpu
                elif have_cpu:
                    result['cpu_seconds_estimated'] = cpu_partial
            if result.get('gpu_seconds') is None:
                if all_gpu:
                    result['gpu_seconds'] = gpu
                elif have_gpu:
                    result['gpu_seconds_estimated'] = gpu_partial
            result['resource_metrics_partial'] = value.get('state') == 'running' or any(r['status'] == 'running' for r in rows) or not all_cpu
            if result.get('gpu_seconds') is None:
                result.setdefault('gpu_metrics_status', None)
                if not result['gpu_metrics_status']:
                    result['gpu_metrics_status'] = 'profiled_kernels_diagnostic' if have_gpu else 'counter_unavailable'
            return result
    except (OSError, sqlite3.Error):
        # Missing legacy schemas or busy accounting cannot make the queue unavailable.
        return value


class CpuProgress:
    """Best-effort live CPU sample in a private worker progress file; not billing."""
    def __init__(self, env):
        self.path = Path(env['MTA_AI_PROGRESS_FILE']) if env and env.get('MTA_AI_PROGRESS_FILE') and env.get('MTA_AI_SUPERVISOR_CPU_PROGRESS') != '0' else None
        self.last = float('-inf')

    def publish(self, read_cpu):
        import time
        now = time.monotonic()
        if self.path is None or now-self.last < 1:
            return
        self.last = now
        try:
            amount = number(read_cpu())
            if amount is None:
                return
            payload = {}
            if self.path.exists() and self.path.stat().st_size <= 65536:
                try:
                    payload = json.loads(self.path.read_text())
                except (ValueError, OSError):
                    pass
            if not isinstance(payload, dict):
                payload = {}
            payload['cpu_seconds_estimated'] = amount
            from .storage import _atomic_json_write
            _atomic_json_write(self.path, payload)
        except (OSError, ValueError, RuntimeError, TypeError, IndexError, ArithmeticError):
            pass


def process_cpu(pid):
    """Exact process CPU counters sampled from procfs, without host-wide load."""
    import os
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return (int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
