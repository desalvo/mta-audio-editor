"""Per-user AI history visibility and notification inbox; accounting is immutable here."""
from __future__ import annotations
import math
import time
from . import ai_arranger_runtime as runtime

ACTIVE = frozenset(('queued', 'blocked', 'running'))
TERMINAL = frozenset(('completed', 'cancelled', 'failed', 'interrupted'))
FIELDS = ('job_id', 'project_id', 'operation', 'state', 'phase', 'message', 'created_at',
          'started_at', 'completed_at', 'elapsed_seconds', 'queue_position', 'jobs_ahead',
          'cancel_requested', 'progress_percent', 'progress_source', 'progress_estimated',
          'steps_completed', 'steps_total', 'cpu_seconds', 'gpu_seconds',
          'cpu_seconds_estimated', 'gpu_seconds_estimated', 'gpu_metrics_status', 'gpu_metrics_source')


def _tables(con):
    con.execute('''CREATE TABLE IF NOT EXISTS job_ui_state (
        actor_id INTEGER NOT NULL, job_id TEXT NOT NULL, hidden INTEGER NOT NULL DEFAULT 0,
        notified INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(actor_id,job_id))''')
    con.execute('''CREATE TABLE IF NOT EXISTS job_ui_viewers (
        actor_id INTEGER PRIMARY KEY, notifications_since REAL NOT NULL)''')


def _number(value, name):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid ' + name)
    return float(value)


def select(actor_id, can_access, body=None):
    body = body or {}
    mode = body.get('mode', 'all')
    if mode not in ('all', 'selected', 'range', 'count'):
        raise ValueError('Invalid job selection')
    ids = body.get('ids', [])
    if not isinstance(ids, list) or len(ids) > 5000 or any(not isinstance(x, str) or not runtime._SAFE_JOB_ID.fullmatch(x) for x in ids):
        raise ValueError('Invalid job selection IDs')
    excluded = body.get('exclude_ids', [])
    if not isinstance(excluded, list) or len(excluded) > 100000 or any(not isinstance(x, str) or not runtime._SAFE_JOB_ID.fullmatch(x) for x in excluded):
        raise ValueError('Invalid excluded job IDs')
    excluded = set(excluded)
    ids = set(ids)
    count = body.get('count', 100)
    if type(count) is not int or not 1 <= count <= 5000:
        raise ValueError('Job count must be 1–5000')
    start, end = _number(body.get('start'), 'start'), _number(body.get('end'), 'end')
    if mode == 'range' and (start is None or end is None or start >= end):
        raise ValueError('A valid creation date interval is required')
    if start is not None and end is not None and start >= end:
        raise ValueError('Invalid date interval')
    state = body.get('state', 'all')
    if state not in ACTIVE | TERMINAL | {'all', 'active', 'terminal'}:
        raise ValueError('Invalid job state')
    with runtime._db() as con:
        _tables(con)
        runtime._recover_dead_runners(con)
        rows = con.execute('''SELECT j.* FROM jobs j LEFT JOIN job_ui_state u
          ON u.job_id=j.job_id AND u.actor_id=? WHERE COALESCE(u.hidden,0)=0
          ORDER BY j.created_at DESC,j.job_id DESC''', (actor_id,)).fetchall()
    queue = sorted((dict(row) for row in rows if row['state'] == 'queued'), key=lambda row: (row['rank'], row['created_at'], row['job_id']))
    positions = {row['job_id']: index+1 for index, row in enumerate(queue)}
    access = {}
    result = []
    for raw in rows:
        row = dict(raw)
        if row['job_id'] in positions:
            row['queue_position'] = positions[row['job_id']]
            row['jobs_ahead'] = row['queue_position']-1
        pid = row['project_id']
        if pid not in access:
            access[pid] = bool(can_access(pid))
        own_remote=(pid=='remote-user-'+str(actor_id) and row.get('actor_user_id')==actor_id
                    and row['operation'].startswith('worker:'))
        if not access[pid] and not own_remote:
            continue
        if row['job_id'] in excluded:
            continue
        if mode == 'selected' and row['job_id'] not in ids:
            continue
        if start is not None and row['created_at'] < start or end is not None and row['created_at'] >= end:
            continue
        if state == 'active' and row['state'] not in ACTIVE or state == 'terminal' and row['state'] not in TERMINAL:
            continue
        if state not in ('all', 'active', 'terminal') and row['state'] != state:
            continue
        # Restrict count selection to rows compatible with the requested action.
        if mode == 'count' and body.get('action') == 'archive' and row['state'] not in TERMINAL:
            continue
        if mode == 'count' and body.get('action') == 'cancel' and row['state'] not in ACTIVE:
            continue
        result.append(row)
        if mode == 'count' and len(result) >= count:
            break
    return result


def bulk(actor_id, can_access, body):
    if body.get('action') not in ('archive', 'cancel') or type(body.get('preview', False)) is not bool:
        raise ValueError('Invalid bulk action')
    rows = select(actor_id, can_access, body)
    states = TERMINAL if body['action'] == 'archive' else ACTIVE
    eligible = [row for row in rows if row['state'] in states]
    batch = eligible[:5000]
    if body.get('preview'):
        return {'matched': len(rows), 'eligible': len(eligible), 'skipped': len(rows)-len(eligible),
                'ids': [row['job_id'] for row in batch], 'truncated': len(eligible) > len(batch)}
    changed, skipped, errors = 0, len(rows)-len(eligible), []
    if body['action'] == 'archive':
        # Hide only from this user's operational history. Keep queue records,
        # terminal receipts, metering, publications and invoices for recovery/audit.
        with runtime._db() as con:
            _tables(con)
            con.execute('BEGIN IMMEDIATE')
            for row in batch:
                current = con.execute('SELECT state FROM jobs WHERE job_id=?', (row['job_id'],)).fetchone()
                if current is None or current[0] not in TERMINAL:
                    skipped += 1
                    continue
                con.execute('''INSERT INTO job_ui_state(actor_id,job_id,hidden) VALUES(?,?,1)
                    ON CONFLICT(actor_id,job_id) DO UPDATE SET hidden=1''', (actor_id, row['job_id']))
                changed += 1
            con.execute('COMMIT')
    else:
        for row in batch:
            try:
                job = runtime.cancel(row['job_id'])
                if job and (job['state'] == 'cancelled' or job.get('cancel_requested')):
                    changed += 1
                else:
                    skipped += 1
            except ValueError:
                errors.append({'job_id': row['job_id'], 'reason': 'Worker does not support confirmed cancellation'})
    return {'changed': changed, 'skipped': skipped, 'errors': errors, 'truncated': len(eligible) > len(batch),
            'accounting_preserved': True}


def feed(actor_id, can_access, body=None, *, limit=100, offset=0):
    if type(offset) is not int or offset < 0:
        raise ValueError('Invalid page offset')
    first_seen = time.time()
    with runtime._db() as con:
        _tables(con)
        con.execute('INSERT OR IGNORE INTO job_ui_viewers VALUES(?,?)', (actor_id, first_seen))
    rows = select(actor_id, can_access, body)
    limit = max(1, min(500, int(limit)))
    # Active work is never pushed off the page by a long history.
    active = [row for row in rows if row['state'] in ACTIVE]
    terminal = [row for row in rows if row['state'] in TERMINAL]
    with runtime._db() as con:
        _tables(con)
        since = con.execute('SELECT notifications_since FROM job_ui_viewers WHERE actor_id=?', (actor_id,)).fetchone()[0]
        acknowledged = {row[0] for row in con.execute('SELECT job_id FROM job_ui_state WHERE actor_id=? AND notified=1', (actor_id,))}
    # Query notification candidates independently from UI filters and pagination.
    notifications = []
    all_rows = select(actor_id, can_access)
    for row in all_rows:
        if row['state'] in TERMINAL and (row['completed_at'] or 0) >= since and row['job_id'] not in acknowledged:
            notifications.append({key: row.get(key) for key in FIELDS if key in row})
            if len(notifications) >= 50:
                break
    def public(row):
        # Live sidecars are read only for displayed active jobs.
        value = runtime._with_live_progress(row)
        value['elapsed_seconds'] = max(0, (row['completed_at'] or time.time())-(row['started_at'] or time.time()))
        return {key: value[key] for key in FIELDS if key in value}
    return {'actor_id': actor_id, 'jobs': [public(row) for row in (active+terminal)[offset:offset+limit]],
            'total': len(rows), 'active_count': sum(row['state'] in ACTIVE for row in all_rows), 'notifications': notifications,
            'limit': limit, 'offset': offset, 'has_more': offset+limit < len(rows), 'max_concurrent_jobs': runtime._limit(), 'accounting_preserved': True}


def acknowledge(actor_id, can_access, ids):
    rows = select(actor_id, can_access, {'mode': 'selected', 'ids': ids})
    with runtime._db() as con:
        _tables(con)
        for row in rows:
            if row['state'] in TERMINAL:
                con.execute('''INSERT INTO job_ui_state(actor_id,job_id,notified) VALUES(?,?,1)
                  ON CONFLICT(actor_id,job_id) DO UPDATE SET notified=1''', (actor_id, row['job_id']))
    return {'ok': True}
