"""Operator-accepted job estimates, explicitly distinct from verified telemetry.

Only internal successful-job settlement seals evidence. Numbers are not promoted
from API requests, wall time, anonymous host utilization, failed or missing reports.
"""
import json
import os
from .auth import db

SOURCE='diagnostic-estimate'


def enabled():return os.getenv('MTA_TRUST_AI_DIAGNOSTIC_ESTIMATES','true').lower() in {'1','true','yes','on'}


def promote(job_id,usage,source):
    from . import ai_billing
    values=ai_billing._validate_usage(usage)
    if not enabled() or source in ('gpu-agent','gpu-kernel-verified',SOURCE):return values,source
    if {'gpu_seconds','gpu_energy_joules'}&values.keys():raise ValueError('Untrusted GPU input cannot be promoted')
    with db() as con:
        ai_billing._init(con)
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE name='ai_compute_job_diagnostics'").fetchone()
        row=con.execute('SELECT payload FROM ai_compute_job_diagnostics WHERE job_id=?',(job_id,)).fetchone() if exists else None
        if not row:return values,source
        job=con.execute('SELECT id,status FROM ai_compute_jobs WHERE id=?',(job_id,)).fetchone()
        if not job or job['status']!='running':raise ValueError('Running server job required for estimates')
        try:report=json.loads(row[0])
        except (ValueError,TypeError):return values,source
        if not isinstance(report,dict):return values,source
        estimated=[]
        for metric in ('cpu_seconds','gpu_seconds'):
            key=metric+'_estimated'
            if metric not in values and key in report:
                # Revalidate even previously sanitized persistent records.
                try:candidate=ai_billing._validate_usage({metric:report[key]})
                except (ValueError,TypeError):continue
                if metric=='gpu_seconds' and candidate[metric]<=0:continue
                values.update(candidate);estimated.append(metric)
        if not estimated:return values,source
        envelope=json.dumps({'usage':values,'estimated_resources':estimated},sort_keys=True,allow_nan=False)
        con.execute('BEGIN IMMEDIATE')
        from .worker_loss_resolution import note_evidence_in_transaction
        note_evidence_in_transaction(con,job_id)
        con.execute('CREATE TABLE IF NOT EXISTS ai_trusted_estimate_evidence(job_id TEXT PRIMARY KEY REFERENCES ai_compute_jobs(id) ON DELETE CASCADE,envelope TEXT NOT NULL)')
        prior=con.execute('SELECT envelope FROM ai_trusted_estimate_evidence WHERE job_id=?',(job_id,)).fetchone()
        if prior and prior[0]!=envelope:raise ValueError('Conflicting estimate evidence')
        if not prior:con.execute('INSERT INTO ai_trusted_estimate_evidence VALUES(?,?)',(job_id,envelope))
    return values,SOURCE


def require_evidence(job_id,usage):
    from .ai_billing import _validate_usage
    values=_validate_usage(usage)
    with db() as con:
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE name='ai_trusted_estimate_evidence'").fetchone()
        row=con.execute('SELECT envelope FROM ai_trusted_estimate_evidence WHERE job_id=?',(job_id,)).fetchone() if exists else None
    if not row or json.loads(row[0])['usage']!=values or 'gpu_energy_joules' in values:
        raise ValueError('Trusted estimates require immutable server job evidence')
