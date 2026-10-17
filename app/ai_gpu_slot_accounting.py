"""Agentless GPU slot accounting for a centrally scheduled, single GPU.

An allocated slot is a contractual service unit, NOT hardware utilization.
No measured GPU fields or billing invoice tables are modified here. Slots are
allocated explicitly by the trusted server only, never by untrusted workers.
"""
from __future__ import annotations

import math
import os
import time
from .auth import db

METHOD = 'agentless-equal-slot-v1'


def slot_enabled_for_kind(kind: str) -> bool:
    """Strictly operator-controlled opt-in. Does not infer GPU from user plans."""
    if os.getenv('MTA_AI_GPU_SLOT_TRACKING_ENABLED', '').lower() != 'true':
        return False
    configured = {item.strip() for item in os.getenv('MTA_AI_GPU_SLOT_KINDS', '').split(',') if item.strip()}
    from .ai_worker_registry import registered_kinds
    return kind in registered_kinds() and kind in configured



def _init(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS ai_gpu_slot_leases (
      job_id TEXT PRIMARY KEY REFERENCES ai_compute_jobs(id),
      gpu_key TEXT NOT NULL,
      acquired_ms INTEGER NOT NULL,
      released_ms INTEGER,
      state TEXT NOT NULL CHECK(state IN ('active','released','aborted')),
      method TEXT NOT NULL,
      CHECK(released_ms IS NULL OR released_ms >= acquired_ms)
    );
    CREATE INDEX IF NOT EXISTS idx_gpu_slot_leases_device
      ON ai_gpu_slot_leases(gpu_key,acquired_ms,released_ms);
    CREATE TABLE IF NOT EXISTS ai_gpu_slot_quotes (
      job_id TEXT PRIMARY KEY REFERENCES ai_compute_jobs(id),
      method TEXT NOT NULL,
      slot_seconds REAL NOT NULL,
      micro_eur INTEGER NOT NULL,
      rate_micro_per_second INTEGER NOT NULL,
      calculated_at INTEGER NOT NULL,
      detail_json TEXT NOT NULL
    );
    ''')


def _stamp(value):
    if value is None:
        return int(time.time() * 1000)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError('Invalid millisecond timestamp')
    return value


def _gpu_key(value):
    if not isinstance(value, str) or not (1 <= len(value) <= 64) or not all(
        char.isalnum() or char in '_-.' for char in value
    ):
        raise ValueError('Invalid logical GPU identifier')
    return value


def acquire(job_id: str, gpu_key: str = 'gpu0', *, at_ms: int | None = None):
    """Acquire only after scheduling has granted a GPU slot; never while queued."""
    _gpu_key(gpu_key)
    start = _stamp(at_ms)
    with db() as c:
        _init(c)
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT status FROM ai_compute_jobs WHERE id=?', (job_id,)).fetchone()
        if not row or row['status'] != 'running':
            raise ValueError('GPU lease requires a running registered job')
        if c.execute('SELECT 1 FROM ai_gpu_slot_leases WHERE job_id=?', (job_id,)).fetchone():
            raise ValueError('GPU lease already exists')
        c.execute('INSERT INTO ai_gpu_slot_leases VALUES (?,?,?,?,?,?)',
                  (job_id,gpu_key,start,None,'active',METHOD))
    return {'job_id': job_id, 'gpu_key': gpu_key, 'acquired_ms': start}


def release(job_id: str, *, at_ms: int | None = None, aborted: bool = False):
    end = _stamp(at_ms)
    if not isinstance(aborted, bool):
        raise ValueError('Invalid aborted flag')
    with db() as c:
        _init(c)
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT acquired_ms,state FROM ai_gpu_slot_leases WHERE job_id=?',
                        (job_id,)).fetchone()
        if not row or row['state'] != 'active' or end < row['acquired_ms']:
            raise ValueError('No active slot lease or invalid release time')
        c.execute('UPDATE ai_gpu_slot_leases SET released_ms=?,state=? WHERE job_id=? AND state=?',
                  (end,'aborted' if aborted else 'released',job_id,'active'))
    return {'job_id':job_id,'released_ms':end,'aborted':aborted}


def _seconds_by_job(rows, start_ms, end_ms):
    """Split one logical device's slot capacity equally over active leases.

    Abort intervals remain an explicit service allocation until termination;
    charging policy can exclude them separately. A missing end prevents quotes.
    """
    events = []
    for row in rows:
        begin = max(start_ms,row['acquired_ms'])
        finish = min(end_ms,row['released_ms'])
        if begin < finish:
            events.extend(((begin,1,row['job_id']), (finish,-1,row['job_id'])))
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    active = set()
    values = {r['job_id']:0.0 for r in rows}
    prev = start_ms
    for stamp, change, job_id in events:
        if stamp > prev and active:
            share = (stamp-prev) / (1000.0 * len(active))
            for key in active:
                values[key] += share
        if change == -1:
            active.remove(job_id)
        else:
            active.add(job_id)
        prev = stamp
    return values


def preview(gpu_key: str = 'gpu0', *, start_ms: int, end_ms: int,
            rate_micro_per_second: int = 0):
    """A non-monetized-by-default estimate; not an invoice or a GPU measurement.

    Refuses incomplete active leases overlapping the requested time window.
    Only jobs owned by the MTA scheduler count; external use is NOT measurable.
    """
    _gpu_key(gpu_key)
    start, end = _stamp(start_ms), _stamp(end_ms)
    if end <= start or end-start > 366 * 86400 * 1000:
        raise ValueError('Invalid accounting window')
    if isinstance(rate_micro_per_second, bool) or not isinstance(rate_micro_per_second,int) or not 0 <= rate_micro_per_second <= 10**12:
        raise ValueError('Invalid agentless rate')
    with db() as c:
        _init(c)
        rows = c.execute('''SELECT l.*,j.user_id,j.status,j.billable FROM ai_gpu_slot_leases l
            JOIN ai_compute_jobs j ON j.id=l.job_id
            WHERE l.gpu_key=? AND l.acquired_ms<? AND
                (l.released_ms>? OR l.released_ms IS NULL)
            ORDER BY l.acquired_ms,l.job_id''',(gpu_key,end,start)).fetchall()
    if any(r['released_ms'] is None for r in rows):
        raise ValueError('Active slot leases intersect accounting window')
    if any(r['status'] == 'running' for r in rows):
        raise ValueError('Unfinalized AI job intersects accounting window')
    secs = _seconds_by_job(rows,start,end)
    results = []
    for r in rows:
        seconds = secs[r['job_id']]
        # No charge for cancelled/failed jobs in this conservative policy.
        eligible = r['state'] == 'released' and r['status'] == 'done' and bool(r['billable'])
        charge = round(seconds * rate_micro_per_second) if eligible else 0
        if not math.isfinite(seconds) or charge < 0:
            raise ValueError('Invalid slot accounting calculation')
        results.append({'job_id':r['job_id'],'user_id':r['user_id'],
                        'slot_seconds':round(seconds,9), 'micro_eur':charge,
                        'eligible':eligible,'state':r['state']})
    total = sum(x['slot_seconds'] for x in results)
    if total > (end-start)/1000.0 + 1e-6:
        raise ValueError('GPU capacity conservation violated')
    return {'method': METHOD,'gpu_key':gpu_key,'window_start_ms':start,
            'window_end_ms':end,'rate_micro_per_second':rate_micro_per_second,
            'jobs':results,'total_slot_seconds':round(total,9),
            'total_micro_eur':sum(x['micro_eur'] for x in results),
            'not_an_invoice':True,'external_gpu_activity_unobserved':True}



def priced_period(c, start_ts: int, end_ts: int, *, user_id: int | None = None):
    """Conservative, transactional slot-service charge for a UTC billing interval.

    Shares are calculated across ALL tenants/users on the same logical GPU.
    Each contiguous segment uses the tariff effective at that exact time.
    Returns no physical GPU usage claims; external workloads are not counted.
    Caller must hold the billing transaction for immutable snapshots.
    """
    start_ms, end_ms = start_ts * 1000, end_ts * 1000
    rates = c.execute(
        "SELECT valid_from,valid_until,micro_per_unit FROM ai_resource_price_history "
        "WHERE resource='gpu_slot_seconds_estimated' AND valid_from<? "
        "AND (valid_until IS NULL OR valid_until>?) ORDER BY valid_from",
        (end_ts,start_ts)).fetchall()
    if not rates or not any(r['micro_per_unit'] for r in rates):
        return {'method': METHOD, 'enabled': False, 'total_micro': 0, 'jobs': [],
                'external_gpu_activity_unobserved': True}
    conflicting = c.execute("SELECT 1 FROM ai_resource_price_history WHERE resource='gpu_seconds' "
        "AND micro_per_unit>0 AND valid_from<? AND (valid_until IS NULL OR valid_until>?) LIMIT 1",
        (end_ts,start_ts)).fetchone()
    if conflicting:
        raise ValueError('Measured and estimated GPU tariffs cannot both be active')
    has_leases = bool(c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_gpu_slot_leases'").fetchone())
    leases = c.execute("""SELECT l.*,j.user_id,j.status,j.billable,j.started_at,j.finished_at
        FROM ai_gpu_slot_leases l JOIN ai_compute_jobs j ON j.id=l.job_id
        WHERE l.acquired_ms<? AND (l.released_ms>? OR l.released_ms IS NULL)
        ORDER BY l.gpu_key,l.acquired_ms,l.job_id""", (end_ms,start_ms)).fetchall() if has_leases else []
    if os.getenv('MTA_AI_GPU_SLOT_TRACKING_ENABLED', '').lower() == 'true':
        kinds = {k.strip() for k in os.getenv('MTA_AI_GPU_SLOT_KINDS', '').split(',') if k.strip()}
        if kinds:
            expected = c.execute('SELECT id,kind FROM ai_compute_jobs WHERE started_at>=? '
                                 "AND started_at<? AND billable=1 AND status=\'done\'",
                                 (start_ts,end_ts)).fetchall()
            leased_ids = {r['job_id'] for r in leases}
            if any(j['kind'] in kinds and j['id'] not in leased_ids for j in expected):
                raise ValueError('A configured GPU worker job has no allocated slot evidence')
    # Detect missing, partial, or unfinalized evidence BEFORE calculating any amounts.
    for r in leases:
        if r['released_ms'] is None or r['state'] == 'active' or r['status'] == 'running':
            raise ValueError('Active GPU slot prevents priced billing')
        if r['acquired_ms'] < start_ms or r['released_ms'] > end_ms:
            raise ValueError('GPU slot crosses a priced billing boundary')
        if r['started_at'] < start_ts or r['finished_at'] is None or r['finished_at'] >= end_ts:
            raise ValueError('GPU slot job crosses a billing boundary')
    # Never infer a free GPU service from an untracked GPU job. Operators opt in
    # explicitly to the tracked worker kinds; closed snapshots retain evidence.
    relevant = sorted({r['gpu_key'] for r in leases})
    cuts = {start_ms,end_ms}
    for r in rates:
        for stamp in (r['valid_from'],r['valid_until']):
            if stamp is not None and start_ts < stamp < end_ts:
                cuts.add(stamp*1000)
    per_job = {}
    for gpu in relevant:
        device = [r for r in leases if r['gpu_key']==gpu]
        bounds = set(cuts)
        for row in device:
            bounds.update((row['acquired_ms'],row['released_ms']))
        times = sorted(bounds)
        for lo,hi in zip(times,times[1:]):
            if hi <= lo:
                continue
            active = [r for r in device if r['acquired_ms'] <= lo and r['released_ms'] >= hi]
            if not active:
                continue
            tariff = next((r['micro_per_unit'] for r in rates
                           if r['valid_from']*1000 <= lo and
                           (r['valid_until'] is None or r['valid_until']*1000 > lo)),0)
            share = (hi-lo)/1000/len(active)
            for r in active:
                entry = per_job.setdefault(r['job_id'], {
                    'job_id':r['job_id'], 'user_id':r['user_id'], 'gpu_key':gpu,
                    'slot_seconds':0., 'micro_eur_unrounded':0., 'eligible': bool(
                        r['state']=='released' and r['status']=='done' and r['billable'])})
                entry['slot_seconds'] += share
                if entry['eligible']:
                    entry['micro_eur_unrounded'] += share*tariff
    jobs = []
    for entry in per_job.values():
        if user_id is not None and entry['user_id'] != user_id:
            continue
        jobs.append({key:value for key,value in entry.items() if key!='micro_eur_unrounded'} |
                    {'slot_seconds':round(entry['slot_seconds'],9),
                     'micro_eur':round(entry['micro_eur_unrounded'])})
    return {'method':METHOD,'enabled':True,'total_micro':sum(j['micro_eur'] for j in jobs),
            'jobs':sorted(jobs,key=lambda x:x['job_id']),
            'external_gpu_activity_unobserved':True,
            'unit':'estimated_gpu_slot_seconds_not_hardware_utilization'}


def recover_stale_leases(*, now_ms: int | None = None, older_than_ms: int = 3_600_000,
                         dry_run: bool = True) -> dict:
    """Manual operator recovery after confirming affected worker processes stopped.

    Never runs automatically: PID/host migration may leave a worker active.
    Leases are aborted and remain excluded from monetary previews.
    """
    now = _stamp(now_ms)
    if isinstance(older_than_ms, bool) or not isinstance(older_than_ms, int) or older_than_ms < 3_600_000:
        raise ValueError('Minimum stale lease age is one hour')
    if not isinstance(dry_run, bool):
        raise ValueError('Invalid dry-run flag')
    cutoff = now - older_than_ms
    with db() as c:
        _init(c)
        if not dry_run:
            c.execute('BEGIN IMMEDIATE')
        rows = c.execute("SELECT job_id,gpu_key,acquired_ms FROM ai_gpu_slot_leases "
                         "WHERE state='active' AND acquired_ms<=? ORDER BY acquired_ms,job_id",
                         (cutoff,)).fetchall()
        candidates = [dict(r) for r in rows]
        recovered = []
        if not dry_run:
            for r in candidates:
                updated = c.execute("UPDATE ai_gpu_slot_leases SET state='aborted', released_ms=? "
                                    "WHERE job_id=? AND state='active' AND acquired_ms<=?",
                                    (now,r['job_id'],cutoff))
                if updated.rowcount == 1:
                    recovered.append(r['job_id'])
    return {'dry_run':dry_run,'candidates':candidates,'recovered_job_ids':recovered,
            'cutoff_ms':cutoff,'not_an_invoice':True}
