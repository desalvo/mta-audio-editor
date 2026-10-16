"""Optional task-bound ROCm activity for trusted unified workers; never billing."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
from .ace_gpu_profiler import TaskProfiler, parse_report

REPORT = 'gpu-profile.json'


def _raw(folder):
    from .ai_worker_artifacts import _read_private_file
    return json.loads(_read_private_file(folder / REPORT, 8192))


def enabled():
    return os.getenv('MTA_AI_TORCH_PROFILER', '').lower() in ('1', 'true', 'yes')


def profile_call(folder: Path, task: str, call):
    if not enabled():
        return call()

    previous = None
    try:
        candidate = _raw(folder)
        parse_report(candidate, task, source='torch-profiler')
        previous = candidate
    except (OSError, ValueError, TypeError, RuntimeError):
        previous = None

    def publish(record):
        if previous is not None:
            # SAM singer invocations run sequentially in separate processes.
            # Sum their disjoint capture windows, never just report the last singer.
            if previous['status'] not in ('profiled_kernels_diagnostic', 'profiler_no_gpu_events'):
                record['status'] = 'profiler_failed'
            elif (previous.get('kernel_count', 0) and record.get('kernel_count', 0)
                    and previous.get('device_id') != record.get('device_id')):
                record['status'] = 'profiler_failed'
            else:
                for key in ('gpu_active_seconds', 'kernel_count', 'wall_seconds'):
                    record[key] = record.get(key, 0) + previous.get(key, 0)
                if previous.get('kernel_count', 0):
                    record['device_id'] = previous['device_id']
                if record['status'] == 'profiler_no_gpu_events' and record['kernel_count']:
                    record['status'] = 'profiled_kernels_diagnostic'
        # Same fixed private job directory as request/output. No prompt or raw trace.
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=folder, prefix='.gpu-', delete=False) as handle:
                name = handle.name
                os.fchmod(handle.fileno(), 0o600)
                json.dump(record, handle, allow_nan=False)
            os.replace(name, folder / REPORT)
        finally:
            if name:
                Path(name).unlink(missing_ok=True)

    collector = TaskProfiler(source='torch-profiler', on_update=publish)
    return collector.wrap(lambda *, job_id: call())(job_id=task)


def read_report(folder: Path, task: str):
    if not enabled():
        return {}
    try:
        return parse_report(_raw(folder), task, source='torch-profiler')
    except (OSError, ValueError, TypeError, RuntimeError):
        return {}


def store_report(job_id, report):
    """Separate bounded diagnostics table; never mutate ledger usage or prices."""
    from .auth import db
    with db() as connection:
        connection.execute('''CREATE TABLE IF NOT EXISTS ai_gpu_diagnostics
            (job_id TEXT PRIMARY KEY, report_json TEXT NOT NULL, updated_at INTEGER NOT NULL)''')
        connection.execute('''INSERT OR REPLACE INTO ai_gpu_diagnostics VALUES (?, ?, unixepoch())''',
                           (job_id, json.dumps({**report, 'billing_eligible': False}, allow_nan=False)))
        connection.execute('''DELETE FROM ai_gpu_diagnostics WHERE job_id NOT IN
            (SELECT job_id FROM ai_gpu_diagnostics ORDER BY updated_at DESC, job_id LIMIT 512)''')


def recent_reports():
    from .auth import db
    with db() as connection:
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE name='ai_gpu_diagnostics'").fetchone()
        if not exists:
            return []
        jobs_exist = connection.execute("SELECT 1 FROM sqlite_master WHERE name='ai_compute_jobs'").fetchone()
        if jobs_exist:
            return [{'job_id': row[0], 'kind': row[2], 'job_status': row[3], **json.loads(row[1])}
                    for row in connection.execute('''SELECT d.job_id,d.report_json,j.kind,j.status
                        FROM ai_gpu_diagnostics d LEFT JOIN ai_compute_jobs j ON j.id=d.job_id
                        ORDER BY d.updated_at DESC LIMIT 50''')]
        return [{'job_id': row[0], **json.loads(row[1])} for row in connection.execute(
            'SELECT job_id,report_json FROM ai_gpu_diagnostics ORDER BY updated_at DESC LIMIT 50')]
