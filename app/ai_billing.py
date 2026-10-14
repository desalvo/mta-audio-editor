"""Durable AI job ledger and immutable billing snapshots.

CPU/GPU figures are ingested from a trusted worker metering source, never
inferred from request latency. Prices are stored as integer micro-units.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sqlite3
import time
import uuid
from .auth import db
from contextlib import contextmanager

@contextmanager
def _borrow_connection(connection):
    """Keep reads on the caller transaction; never commit or close it."""
    yield connection

UNITS = ('cpu_seconds', 'gpu_seconds', 'gpu_energy_joules', 'gpu_slot_seconds_estimated', 'disk_gb_hours', 'disk_read_bytes', 'disk_write_bytes', 'request_bytes', 'response_bytes')
PERIODS = ('day', 'week', 'month', 'year', 'custom')
# Per-process I/O includes temporary files and is diagnostic ONLY.
# Billable storage must be based on persistent, user-owned assets.
NON_BILLABLE_IO = frozenset({'disk_read_bytes', 'disk_write_bytes', 'gpu_energy_joules'})
# Energy is retained as telemetry only; GPU billing uses verified gpu_seconds.


def _init(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS ai_resource_prices (
      resource TEXT PRIMARY KEY, micro_per_unit INTEGER NOT NULL DEFAULT 0 CHECK(micro_per_unit>=0),
      currency TEXT NOT NULL DEFAULT 'EUR', updated_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS ai_resource_price_history (
      id INTEGER PRIMARY KEY,
      resource TEXT NOT NULL,
      valid_from INTEGER NOT NULL,
      valid_until INTEGER,
      micro_per_unit INTEGER NOT NULL CHECK(micro_per_unit>=0),
      currency TEXT NOT NULL DEFAULT 'EUR',
      CHECK(valid_until IS NULL OR valid_until > valid_from),
      UNIQUE(resource,valid_from));
    CREATE INDEX IF NOT EXISTS idx_ai_rates_lookup ON ai_resource_price_history(resource,valid_from,valid_until);
    CREATE TABLE IF NOT EXISTS ai_compute_jobs (
      id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, token_id INTEGER,
      kind TEXT NOT NULL, status TEXT NOT NULL, started_at INTEGER NOT NULL,
      finished_at INTEGER, wall_ms INTEGER NOT NULL DEFAULT 0,
      usage_json TEXT NOT NULL DEFAULT '{}', resource_source TEXT NOT NULL DEFAULT 'unmetered',
      billable INTEGER NOT NULL DEFAULT 1 CHECK(billable IN (0,1)),
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE INDEX IF NOT EXISTS idx_ai_compute_user_time ON ai_compute_jobs(user_id,started_at);
    CREATE TABLE IF NOT EXISTS ai_persistent_storage_samples (
      id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, sampled_at INTEGER NOT NULL,
      bytes_used INTEGER NOT NULL CHECK(bytes_used>=0),
      source TEXT NOT NULL DEFAULT 'persistent-user-store',
      UNIQUE(user_id,sampled_at),
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE INDEX IF NOT EXISTS idx_ai_storage_user_time ON ai_persistent_storage_samples(user_id,sampled_at);
    CREATE TABLE IF NOT EXISTS ai_billing_schedules (
      id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL UNIQUE, cadence TEXT NOT NULL,
      enabled INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS ai_billing_periods (
      id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
      start_ts INTEGER NOT NULL, end_ts INTEGER NOT NULL,
      currency TEXT NOT NULL, total_micro INTEGER NOT NULL,
      snapshot_json TEXT NOT NULL, created_at INTEGER NOT NULL,
      UNIQUE(user_id,start_ts,end_ts,currency),
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    ''')
    c.execute("""CREATE TABLE IF NOT EXISTS ai_job_hardware_snapshots (
      job_id TEXT PRIMARY KEY REFERENCES ai_compute_jobs(id) ON DELETE CASCADE,
      captured_at INTEGER NOT NULL, model_version TEXT NOT NULL,
      cpu_model TEXT, gpu_model TEXT, cpu_rate_micro INTEGER,
      gpu_rate_micro INTEGER, storage_rate_micro INTEGER,
      origin TEXT NOT NULL CHECK(origin IN ('local-advisory','unknown'))
    )""")
    c.execute('''CREATE TABLE IF NOT EXISTS ai_user_billing_settings (
      user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
      enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
      changed_at INTEGER NOT NULL
    )''')
    # Safe additive upgrade for deployed SQLite ledgers. No record is deleted.
    columns = {r[1] for r in c.execute('PRAGMA table_info(ai_compute_jobs)')}
    if 'billable' not in columns:
        c.execute('ALTER TABLE ai_compute_jobs ADD COLUMN billable INTEGER NOT NULL DEFAULT 1 CHECK(billable IN (0,1))')
        # Existing test records retain their measured usage but never incur charges.
        c.execute("UPDATE ai_compute_jobs SET billable=0 WHERE kind='accounting_validation'")
        c.commit()


def user_billing_enabled(user_id: int, *, _connection=None) -> bool:
    with (db() if _connection is None else _borrow_connection(_connection)) as c:
        if _connection is None:
            _init(c)
        row = c.execute('SELECT enabled FROM ai_user_billing_settings WHERE user_id=?', (user_id,)).fetchone()
        return bool(row and row['enabled'])


def set_user_billing_enabled(user_id: int, enabled: bool) -> dict:
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError('Invalid user ID')
    if not isinstance(enabled, bool):
        raise ValueError('enabled must be boolean')
    with db() as c:
        _init(c)
        c.execute('BEGIN IMMEDIATE')
        if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1', (user_id,)).fetchone():
            raise ValueError('Active user required')
        c.execute('INSERT INTO ai_user_billing_settings(user_id,enabled,changed_at) VALUES(?,?,?) '
                  'ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled,changed_at=excluded.changed_at',
                  (user_id,int(enabled),int(time.time())))
    return {'user_id':user_id,'billing_enabled':enabled}


def user_billing_settings() -> list[dict]:
    with db() as c:
        _init(c)
        return [dict(r) for r in c.execute('SELECT user_id,enabled,changed_at FROM ai_user_billing_settings ORDER BY user_id')]


def _validate_usage(values):
    """Accept only finite, bounded telemetry without coercing malformed input.

    In particular, an explicit empty list must not become an empty measurement
    via the legacy ``usage or {}`` fallback in finalization entrypoints.
    """
    if not isinstance(values, dict) or set(values) - (set(UNITS) - {'gpu_slot_seconds_estimated'}):
        raise ValueError('Unsupported resource field')
    clean = {}
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError('Resource values must be finite nonnegative numbers')
        try:
            number = float(value)
        except (OverflowError, ValueError) as exc:
            raise ValueError('Resource values must be finite nonnegative numbers') from exc
        if not math.isfinite(number) or not (0 <= number < 1e18):
            raise ValueError('Resource values must be finite nonnegative numbers')
        clean[key] = number
    return clean


def create_job(user_id: int, kind: str, token_id=None, *, started_at=None, diagnostic=False):
    if not isinstance(kind, str) or not (1 <= len(kind) <= 72) or not all(c.isalnum() or c in '_-.' for c in kind):
        raise ValueError('Invalid job kind')
    if not isinstance(diagnostic, bool):
        raise ValueError('diagnostic must be boolean')
    job_id = uuid.uuid4().hex
    with db() as c:
        _init(c)
        if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1', (user_id,)).fetchone():
            raise ValueError('User missing or inactive')
        stamp = int(time.time() if started_at is None else started_at)
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM ai_billing_periods WHERE user_id=? AND start_ts<=? AND end_ts>? LIMIT 1',
                     (user_id, stamp, stamp)).fetchone():
            raise ValueError('Cannot create a job inside a closed billing interval')
        # Freeze statistical hardware identity at job creation, not at reporting
        # time: a migrated LXC must never reprice past jobs with the new host.
        from .ai_billing_profiles import suggested_prices
        hardware = suggested_prices()
        c.execute('INSERT INTO ai_compute_jobs(id,user_id,token_id,kind,status,started_at,billable) VALUES(?,?,?,?,?,?,?)',
                  (job_id,user_id,token_id,kind,'running',stamp,int(not diagnostic)))
        suggested = hardware['suggested_micro_per_unit']
        cpu_model, gpu_model = hardware['cpu_model'], hardware['gpu_model']
        c.execute('''INSERT INTO ai_job_hardware_snapshots
          (job_id,captured_at,model_version,cpu_model,gpu_model,cpu_rate_micro,
           gpu_rate_micro,storage_rate_micro,origin)
          VALUES(?,?,?,?,?,?,?,?,?)''',
          (job_id,stamp,hardware['model_version'],cpu_model,gpu_model,
           suggested['cpu_seconds'],suggested['gpu_slot_seconds_estimated'],
           suggested['disk_gb_hours'],
           'local-advisory' if cpu_model or gpu_model else 'unknown'))

    return job_id


def existing_inference_ledger_job(inference_job_id: str, user_id: int, kind: str) -> str | None:
    """Find an already provisioned obligation irrespective of current opt-in.

    Turning billing off affects future admissions, not durable jobs already
    accepted into the ledger. This is read-only and never creates a charge.
    """
    if not isinstance(inference_job_id, str) or not (1 <= len(inference_job_id) <= 128) or not all(
            ch.isascii() and (ch.isalnum() or ch in '-_') for ch in inference_job_id):
        raise ValueError('Invalid durable inference ID')
    if type(user_id) is not int or user_id <= 0 or kind not in ('arranger', 'remix'):
        raise ValueError('Invalid inference billing identity')
    ledger_id = uuid.uuid5(uuid.NAMESPACE_URL, 'mta-ai-inference:' + inference_job_id).hex
    with db() as c:
        _init(c)
        record = c.execute('SELECT user_id,kind FROM ai_compute_jobs WHERE id=?', (ledger_id,)).fetchone()
    if record is None:
        return None
    if int(record['user_id']) != user_id or record['kind'] != kind:
        raise ValueError('Conflicting provisioned billing identity')
    return ledger_id


def provision_inference_job(inference_job_id: str, user_id: int, kind: str) -> str | None:
    """Provision a stable ledger identity only when billing is explicitly enabled.

    Multiple retries resolve to the same row and cannot create duplicate jobs.
    This does not by itself bind queue admission or make a cross-database commit.
    """
    if not isinstance(inference_job_id, str) or not (1 <= len(inference_job_id) <= 128) or not all(
            ch.isascii() and (ch.isalnum() or ch in '-_') for ch in inference_job_id):
        raise ValueError('Invalid durable inference ID')
    if type(user_id) is not int or user_id <= 0:
        raise ValueError('Authenticated positive user ID required')
    if kind not in ('arranger', 'remix'):
        raise ValueError('Unsupported billable inference kind')
    from .ai_billing_profiles import suggested_prices
    with db() as c:
        _init(c)
        c.execute('BEGIN IMMEDIATE')
        if not user_billing_enabled(user_id, _connection=c):
            return None
        if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1', (user_id,)).fetchone():
            raise ValueError('Active user required')
        ledger_id = uuid.uuid5(uuid.NAMESPACE_URL, 'mta-ai-inference:' + inference_job_id).hex
        row = c.execute('SELECT user_id,kind FROM ai_compute_jobs WHERE id=?', (ledger_id,)).fetchone()
        if row:
            if int(row['user_id']) != user_id or row['kind'] != kind:
                raise ValueError('Conflicting durable inference billing identity')
            return ledger_id
        stamp = int(time.time())
        if c.execute('SELECT 1 FROM ai_billing_periods WHERE user_id=? AND start_ts<=? AND end_ts>? LIMIT 1',
                     (user_id, stamp, stamp)).fetchone():
            raise ValueError('Cannot provision within closed billing period')
        hardware = suggested_prices()
        rates = hardware['suggested_micro_per_unit']
        c.execute('INSERT INTO ai_compute_jobs(id,user_id,token_id,kind,status,started_at,billable) VALUES(?,?,NULL,?,?,?,1)',
                  (ledger_id, user_id, kind, 'running', stamp))
        c.execute('INSERT INTO ai_job_hardware_snapshots (job_id,captured_at,model_version,cpu_model,gpu_model,cpu_rate_micro,gpu_rate_micro,storage_rate_micro,origin) VALUES(?,?,?,?,?,?,?,?,?)',
                  (ledger_id, stamp, hardware['model_version'], hardware['cpu_model'], hardware['gpu_model'],
                   rates['cpu_seconds'], rates['gpu_slot_seconds_estimated'], rates['disk_gb_hours'],
                   'local-advisory' if hardware['cpu_model'] or hardware['gpu_model'] else 'unknown'))
        return ledger_id


def job_hardware_snapshot(job_id: str) -> dict | None:
    """Return immutable advisory hardware profile captured at job creation."""
    with db() as c:
        _init(c)
        row = c.execute('SELECT * FROM ai_job_hardware_snapshots WHERE job_id=?',
                        (job_id,)).fetchone()
        return dict(row) if row else None


def finish_job(job_id, status, usage=None, *, source='unmetered', finished_at=None):
    if status not in ('done','failed','cancelled'):
        raise ValueError('Invalid final job status')
    values = _validate_usage({} if usage is None else usage)
    if source not in ('unmetered','worker','cgroup','gpu-agent','remote-worker'):
        raise ValueError('Invalid metering source')
    if values and source == 'unmetered':
        raise ValueError('Resources require trusted metering source')
    # A CPU/cgroup worker may not self-certify GPU time or energy. These
    # fields are reserved for a separately authenticated GPU sensor; never
    # accept GPU-looking numbers from the ordinary subprocess collector.
    gpu_fields = {'gpu_seconds', 'gpu_energy_joules'}
    if gpu_fields.intersection(values) and source != 'gpu-agent':
        raise ValueError('GPU measurements require trusted gpu-agent source')
    if source == 'gpu-agent' and not gpu_fields.intersection(values):
        raise ValueError('GPU agent must provide an explicit GPU measurement')
    with db() as c:
        _init(c)
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT user_id,started_at,status FROM ai_compute_jobs WHERE id=?',(job_id,)).fetchone()
        if not row or row['status'] != 'running':
            raise ValueError('Job missing or already finalized')
        end = int(time.time() if finished_at is None else finished_at)
        if end < row['started_at']:
            raise ValueError('End precedes start')
        if c.execute('SELECT 1 FROM ai_billing_periods WHERE user_id=? AND start_ts<? AND end_ts>? LIMIT 1',
                     (row['user_id'], end + 1, row['started_at'])).fetchone():
            raise ValueError('Cannot finalize a job intersecting a closed billing interval')
        # Compare-and-set makes duplicate completion impossible even when two
        # independent workers race to finalize the same job.
        updated = c.execute(
            'UPDATE ai_compute_jobs SET status=?,finished_at=?,wall_ms=?,usage_json=?,resource_source=? '
            "WHERE id=? AND status='running'",
            (status,end,(end-row['started_at'])*1000,json.dumps(values,sort_keys=True),source,job_id))
        if updated.rowcount != 1:
            raise ValueError('Job already finalized by another worker')



def recover_stale_jobs(*, older_than_seconds: int = 86400, now: int | None = None, dry_run: bool = True) -> dict:
    """Inspect or manually quarantine orphaned jobs after worker/server crashes.

    Never run automatically: an old running job could still be processing. An
    operator must verify that the associated workers have stopped before using
    dry_run=False. No CPU/GPU/storage usage is fabricated or charged.
    """
    if (isinstance(older_than_seconds, bool) or not isinstance(older_than_seconds, int)
            or older_than_seconds < 3600):
        raise ValueError('Recovery threshold must be at least one hour')
    if not isinstance(dry_run, bool):
        raise ValueError('dry_run must be boolean')
    current = int(time.time()) if now is None else now
    if isinstance(current, bool) or not isinstance(current, int) or current < 0:
        raise ValueError('Invalid recovery timestamp')
    cutoff = current - older_than_seconds
    with db() as c:
        _init(c)
        if not dry_run:
            c.execute('BEGIN IMMEDIATE')
        rows = c.execute(
            "SELECT id,user_id,kind,started_at FROM ai_compute_jobs "
            "WHERE status='running' AND started_at<=? ORDER BY started_at,id",
            (cutoff,),
        ).fetchall()
        candidates = [{'job_id': r['id'], 'user_id': r['user_id'],
                       'kind': r['kind'], 'started_at': r['started_at']} for r in rows]
        recovered = []
        if not dry_run:
            for job in candidates:
                updated = c.execute(
                    "UPDATE ai_compute_jobs SET status='failed', finished_at=?, wall_ms=?, "
                    "usage_json='{}', resource_source='unmetered' "
                    "WHERE id=? AND status='running' AND started_at<=?",
                    (current, max(0, current-job['started_at'])*1000, job['job_id'], cutoff),
                )
                if updated.rowcount == 1:
                    recovered.append(job['job_id'])
        return {'dry_run': dry_run, 'cutoff': cutoff, 'candidates': candidates,
                'recovered_job_ids': recovered}


def _parse_effective(value, *, default_now=False):
    if value is None:
        if default_now:
            return int(time.time())
        return None
    if isinstance(value, str):
        try:
            if 'T' in value or ' ' in value:
                parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    raise ValueError('Tariff timestamps require an explicit timezone')
                return int(parsed.astimezone(dt.timezone.utc).timestamp())
            return int(dt.datetime.combine(dt.date.fromisoformat(value),dt.time(),tzinfo=dt.timezone.utc).timestamp())
        except (ValueError, OverflowError) as exc:
            raise ValueError('Invalid tariff validity date') from exc
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise ValueError('Invalid tariff validity date')


def set_price(resource, micro_per_unit, currency='EUR', *, valid_from=None, valid_until=None):
    if resource not in UNITS or not isinstance(micro_per_unit,int) or isinstance(micro_per_unit,bool) or micro_per_unit < 0:
        raise ValueError('Invalid price or resource')
    if currency != 'EUR':
        raise ValueError('Only EUR currency supported')
    start = _parse_effective(valid_from,default_now=True)
    end = _parse_effective(valid_until)
    if end is not None and end <= start:
        raise ValueError('Tariff end must follow start')
    with db() as c:
        _init(c)
        c.execute('BEGIN IMMEDIATE')
        # Closed billing periods cannot be silently repriced retroactively.
        if c.execute('SELECT 1 FROM ai_billing_periods WHERE end_ts>? AND start_ts<? LIMIT 1',
                     (start, end if end is not None else 253402300799)).fetchone():
            raise ValueError('Tariff interval intersects an immutable closed billing period')
        # Previous open-ended rate may be superseded at a later effective date.
        c.execute('UPDATE ai_resource_price_history SET valid_until=? WHERE resource=? AND valid_until IS NULL AND valid_from<?', (start,resource,start))
        # Do not allow ambiguous rate selection in overlapping validity windows.
        if c.execute('SELECT 1 FROM ai_resource_price_history WHERE resource=? '
                     'AND (valid_until IS NULL OR valid_until>?) AND (? IS NULL OR valid_from<?) '
                     'AND valid_from!=?',(resource,start,end,end,start)).fetchone():
            raise ValueError('Overlapping tariff validity period')
        current = c.execute('SELECT id FROM ai_resource_price_history WHERE resource=? AND valid_from=?',
                            (resource,start)).fetchone()
        if current:
            c.execute('UPDATE ai_resource_price_history SET micro_per_unit=?, valid_until=? WHERE id=?',
                      (micro_per_unit,end,current['id']))
        else:
            # A new open-ended tariff replaces the previous open-ended tariff
            # only if that previous rate started before the new one.
            previous = c.execute('SELECT id,valid_from FROM ai_resource_price_history WHERE resource=? '
                                 'AND valid_until IS NULL AND valid_from<? ORDER BY valid_from DESC LIMIT 1',
                                 (resource,start)).fetchone()
            if previous:
                c.execute('UPDATE ai_resource_price_history SET valid_until=? WHERE id=?',(start,previous['id']))
            c.execute('INSERT INTO ai_resource_price_history(resource,valid_from,valid_until,micro_per_unit,currency) '
                      'VALUES(?,?,?,?,?)',(resource,start,end,micro_per_unit,currency))
        c.execute('INSERT INTO ai_resource_prices(resource,micro_per_unit,currency,updated_at) VALUES(?,?,?,?) '
                  'ON CONFLICT(resource) DO UPDATE SET micro_per_unit=excluded.micro_per_unit,updated_at=excluded.updated_at',
                  (resource,micro_per_unit,currency,int(time.time())))


def tariff_history(resource=None):
    if resource is not None and resource not in UNITS:
        raise ValueError('Invalid resource')
    with db() as c:
        _init(c)
        if resource is None:
            rows = c.execute('SELECT resource,micro_per_unit,currency,valid_from,valid_until FROM ai_resource_price_history ORDER BY resource,valid_from')
        else:
            rows = c.execute('SELECT resource,micro_per_unit,currency,valid_from,valid_until FROM ai_resource_price_history WHERE resource=? ORDER BY resource,valid_from', (resource,))
        return [dict(r) for r in rows]


def prices(at=None, *, _connection=None):
    stamp = int(time.time() if at is None else at)
    with (db() if _connection is None else _borrow_connection(_connection)) as c:
        if _connection is None:
            _init(c)
        rows=c.execute('SELECT resource,micro_per_unit FROM ai_resource_price_history '
                       'WHERE valid_from<=? AND (valid_until IS NULL OR valid_until>?) '
                       'ORDER BY valid_from DESC',(stamp,stamp)).fetchall()
        result={}
        for r in rows:
            result.setdefault(r['resource'],r['micro_per_unit'])
        return result


def _rates_for_jobs(c, jobs):
    history = [dict(r) for r in c.execute('SELECT resource,micro_per_unit,valid_from,valid_until '
                                         'FROM ai_resource_price_history ORDER BY valid_from DESC')]
    rates = {}
    for job in jobs:
        selected = {}
        for r in history:
            if r['resource'] not in selected and r['valid_from']<=job['started_at'] and (r['valid_until'] is None or job['started_at']<r['valid_until']):
                selected[r['resource']] = r['micro_per_unit']
        rates[job['id']] = selected
    return rates

def _window(period, anchor=None, start=None, end=None):
    if period not in PERIODS:
        raise ValueError('Unknown period')
    if period == 'custom':
        if not start or not end:
            raise ValueError('Custom period requires start/end')
        a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        if b < a or (b-a).days > 3660:
            raise ValueError('Invalid custom period')
        b += dt.timedelta(days=1)
    else:
        a = dt.date.fromisoformat(anchor) if anchor else dt.datetime.now(dt.timezone.utc).date()
        if period == 'day': b = a + dt.timedelta(days=1)
        elif period == 'week':
            a -= dt.timedelta(days=a.weekday()); b = a + dt.timedelta(days=7)
        elif period == 'month':
            a = a.replace(day=1); b = (a.replace(year=a.year+1,month=1) if a.month==12 else a.replace(month=a.month+1))
        else: a, b = a.replace(month=1,day=1), a.replace(year=a.year+1,month=1,day=1)
    utc = dt.timezone.utc
    return int(dt.datetime.combine(a,dt.time(),tzinfo=utc).timestamp()), int(dt.datetime.combine(b,dt.time(),tzinfo=utc).timestamp())


def report(period='month', *, user_id=None, anchor=None, start=None, end=None, _connection=None):
    a,b = _window(period,anchor,start,end)
    with (db() if _connection is None else _borrow_connection(_connection)) as c:
        if _connection is None:
            _init(c)
        rates = prices(_connection=c)
        if user_id is None:
            records = c.execute('SELECT * FROM ai_compute_jobs WHERE started_at>=? AND started_at<? ORDER BY started_at,id', (a,b)).fetchall()
        else:
            records = c.execute('SELECT * FROM ai_compute_jobs WHERE started_at>=? AND started_at<? AND user_id=? ORDER BY started_at,id', (a,b,user_id)).fetchall()
        # Statistics are independent of user opt-in and never authorize charges.
        hardware_by_job = {}
        for rec in records:
            profile = c.execute('SELECT * FROM ai_job_hardware_snapshots WHERE job_id=?',
                                (rec['id'],)).fetchone()
            if profile:
                hardware_by_job[rec['id']] = dict(profile)
        job_rates=_rates_for_jobs(c,records)
        groups={}
        for r in records:
            day=dt.datetime.fromtimestamp(r['started_at'],dt.timezone.utc).strftime('%Y-%m-%d')
            key=(r['user_id'],day)
            row=groups.setdefault(key,{'user_id':r['user_id'],'day':day,'jobs':0,'metered_jobs':0,'cost_micro':0,'suggested_cost_micro':0,'resources':{},'by_type':{}})
            row['jobs']+=1
            if r['resource_source']!='unmetered': row['metered_jobs']+=1
            kind=row['by_type'].setdefault(r['kind'],{'jobs':0,'cost_micro':0})
            kind['jobs']+=1
            vals=json.loads(r['usage_json'])
            cost=0
            for resource,qty in vals.items():
                row['resources'][resource]=row['resources'].get(resource,0)+qty
                # Failed, running, and unmetered jobs may have diagnostic
                # counters; they are never recognized as billable amounts.
                if (r['status']=='done' and r['resource_source']!='unmetered'
                    and r['billable'] == 1
                    and resource not in NON_BILLABLE_IO and resource != 'disk_gb_hours'):
                    cost+=round(qty*job_rates[r['id']].get(resource,0))
            row['cost_micro']+=cost; kind['cost_micro']+=cost
            # Advisory electricity proxy, frozen at job creation. Never an
            # invoice charge and never inferred for an unsuccessful job.
            hardware = hardware_by_job.get(r['id'], {})
            if (r['status'] == 'done' and r['resource_source'] != 'unmetered'
                    and r['billable'] == 1 and hardware.get('cpu_rate_micro') is not None):
                row['suggested_cost_micro'] += round(
                    vals.get('cpu_seconds', 0) * hardware['cpu_rate_micro'])
        # Split storage at *both* UTC midnight and tariff effective-times.
        # A tariff change at 12:00 must not reprice the whole day.
        storage, storage_costs = _priced_storage_usage(c,a,b,user_id)
        for (uid,day), gb_hours in storage.items():
            row=groups.setdefault((uid,day),{'user_id':uid,'day':day,'jobs':0,'metered_jobs':0,'cost_micro':0,'suggested_cost_micro':0,'resources':{},'by_type':{}})
            row['resources']['disk_gb_hours']=round(gb_hours,10)
            # Storage electricity proxy is independent of CPU/GPU model.
            from .ai_billing_profiles import DISK_RATE
            row['suggested_cost_micro'] += round(gb_hours * DISK_RATE)
            row['cost_micro']+=round(storage_costs.get((uid,day),0))
        from .ai_gpu_slot_accounting import priced_period
        slot_service = priced_period(c,a,b,user_id=user_id)
        for gpu_job in slot_service['jobs']:
            origin = next((r for r in records if r['id']==gpu_job['job_id']), None)
            if origin is None:
                raise ValueError('GPU slot accounting job not in requested period')
            day=dt.datetime.fromtimestamp(origin['started_at'],dt.timezone.utc).strftime('%Y-%m-%d')
            key=(gpu_job['user_id'],day)
            row=groups.setdefault(key,{'user_id':gpu_job['user_id'],'day':day,'jobs':0,
                'metered_jobs':0,'cost_micro':0,'suggested_cost_micro':0,'resources':{},'by_type':{}})
            row['cost_micro']+=gpu_job['micro_eur']
            hardware = hardware_by_job.get(gpu_job['job_id'], {})
            if gpu_job.get('eligible') and hardware.get('gpu_rate_micro') is not None:
                row['suggested_cost_micro'] += round(
                    gpu_job['slot_seconds'] * hardware['gpu_rate_micro'])
            row['resources']['gpu_slot_seconds_estimated']=round(
                row['resources'].get('gpu_slot_seconds_estimated',0)+gpu_job['slot_seconds'],9)
        return {'gpu_slot_service':slot_service, 'hardware_by_job':hardware_by_job,
'start_ts':a,'end_ts':b,'currency':'EUR','prices_micro':rates,
                'billing_enabled_users': sorted({r['user_id'] for r in records if user_billing_enabled(r['user_id'],_connection=c)}),
                'rows':list(groups.values()),'total_micro':sum(row['cost_micro'] for row in groups.values()),
                'suggested_total_micro':sum(row['suggested_cost_micro'] for row in groups.values()),
                'suggested_cost_is_advisory':True,
                'job_count':len(records),'diagnostic_jobs':sum(r['billable']==0 for r in records),
                'unmetered_jobs':sum(r['billable']==1 and r['resource_source']=='unmetered' for r in records),
                'running_jobs':sum(r['billable']==1 and r['status']=='running' for r in records),
                'storage_sampling': 'intervals-between-observed-samples-only'}


def record_persistent_storage(user_id: int, bytes_used: int, *, sampled_at=None):
    """Record validated occupied storage, excluding transient and cache files.

    Caller MUST compute this under a trusted, per-user persistent storage
    directory; do not pass host-wide disk utilization or worker I/O.
    """
    if isinstance(bytes_used, bool) or not isinstance(bytes_used,int) or bytes_used < 0:
        raise ValueError('Invalid persistent storage measurement')
    stamp = int(time.time() if sampled_at is None else sampled_at)
    if stamp < 0 or stamp > int(time.time()) + 60:
        raise ValueError('Invalid storage timestamp')
    with db() as c:
        _init(c)
        c.execute('BEGIN IMMEDIATE')
        if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(user_id,)).fetchone():
            raise ValueError('Active user required')
        if c.execute('SELECT 1 FROM ai_billing_periods WHERE user_id=? AND start_ts<=? AND end_ts>?', (user_id,stamp,stamp)).fetchone():
            raise ValueError('Cannot modify a closed billing interval')
        c.execute('INSERT INTO ai_persistent_storage_samples(user_id,sampled_at,bytes_used) VALUES(?,?,?) '
                  'ON CONFLICT(user_id,sampled_at) DO UPDATE SET bytes_used=excluded.bytes_used',
                  (user_id,stamp,bytes_used))


def _storage_usage(c, start: int, end: int, user_id=None):
    """Integrate samples, but only where adjacent measurements bound a period.

    Prevent false billing when no storage telemetry is present or last
    measured storage is unknown. Uses UTC day slices for reporting.
    """
    users = ([user_id] if user_id is not None else
             [r[0] for r in c.execute('SELECT DISTINCT user_id FROM ai_persistent_storage_samples')])
    result = {}
    for uid in users:
        samples=c.execute('SELECT sampled_at,bytes_used FROM ai_persistent_storage_samples WHERE user_id=? AND sampled_at<=? ORDER BY sampled_at',(uid,end)).fetchall()
        for left,right in zip(samples,samples[1:]):
            # Do not assume unchanged storage over an unattended sampling gap.
            if right['sampled_at']-left['sampled_at'] > 26*3600:
                continue
            x=max(start,left['sampled_at']); finish=min(end,right['sampled_at'])
            while x<finish:
                day=dt.datetime.fromtimestamp(x,dt.timezone.utc).date()
                midnight=int(dt.datetime.combine(day+dt.timedelta(days=1),dt.time(),tzinfo=dt.timezone.utc).timestamp())
                nxt=min(finish,midnight)
                key=(uid,day.isoformat())
                result[key]=result.get(key,0)+left['bytes_used']/(1024**3)*(nxt-x)/3600
                x=nxt
    return result


def _priced_storage_usage(c, start: int, end: int, user_id=None):
    """Integrate persistent user storage at tariff boundaries (micro-EUR).

    Only adjacent, timely per-user observations count. No I/O or temporary
    file counters are included. The integration is independent of host load.
    """
    users = ([user_id] if user_id is not None else
             [r[0] for r in c.execute('SELECT DISTINCT user_id FROM ai_persistent_storage_samples')])
    history = [dict(r) for r in c.execute(
        "SELECT valid_from,valid_until,micro_per_unit FROM ai_resource_price_history "
        "WHERE resource='disk_gb_hours' ORDER BY valid_from")]
    quantities, costs = {}, {}
    for uid in users:
        samples = c.execute('SELECT sampled_at,bytes_used FROM ai_persistent_storage_samples '
                            'WHERE user_id=? AND sampled_at<=? ORDER BY sampled_at', (uid,end)).fetchall()
        for left,right in zip(samples,samples[1:]):
            if right['sampled_at']-left['sampled_at'] > 26*3600:
                continue
            x=max(start,left['sampled_at'])
            finish=min(end,right['sampled_at'])
            if x>=finish:
                continue
            gib=left['bytes_used'] / (1024**3)
            while x<finish:
                day=dt.datetime.fromtimestamp(x,dt.timezone.utc).date()
                midnight=int(dt.datetime.combine(day+dt.timedelta(days=1),dt.time(),tzinfo=dt.timezone.utc).timestamp())
                boundaries=[midnight,finish]
                for rate in history:
                    if x<rate['valid_from']<finish:
                        boundaries.append(rate['valid_from'])
                    if rate['valid_until'] is not None and x<rate['valid_until']<finish:
                        boundaries.append(rate['valid_until'])
                nxt=min(boundaries)
                key=(uid,day.isoformat())
                quantity=gib*(nxt-x)/3600
                rate=next((r['micro_per_unit'] for r in reversed(history)
                           if r['valid_from']<=x and (r['valid_until'] is None or x<r['valid_until'])),0)
                quantities[key]=quantities.get(key,0)+quantity
                costs[key]=costs.get(key,0)+quantity*rate
                x=nxt
    return quantities,costs


def measure_persistent_directory(user_id: int, user_root, *, sampled_at=None):
    """Measure only an explicitly assigned user's persistent directory.

    Reject symlinked files/directories to avoid escaping into shared or host
    paths. Exclude known transient names at every depth. No host-wide scan.
    """
    from pathlib import Path
    import stat
    root=Path(user_root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Dedicated persistent user directory required')
    excluded={'.cache','.tmp','tmp','temp','cache','__pycache__','previews','.preview'}
    total=0
    for base,folders,files in os.walk(root,followlinks=False):
        folders[:]=[name for name in folders if name not in excluded and not (Path(base)/name).is_symlink()]
        for name in files:
            file=Path(base)/name
            if name in excluded or name.endswith(('.tmp','.part','.preview')) or file.is_symlink():
                continue
            try:
                info=file.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(info.st_mode):
                total+=info.st_size
    record_persistent_storage(user_id,total,sampled_at=sampled_at)
    return total


def reconcile_period(user_id, start, end):
    """Read-only, fail-closed preflight with actionable anomalies.

    No GPU counter is inferred from elapsed wall time. A success here only
    certifies ledger consistency, not the accuracy of physical sensors.
    """
    a, b = _window('custom', start=start, end=end)
    issues = []

    def issue(code, *, job_id=None, detail=None):
        item = {'code': code}
        if job_id is not None:
            item['job_id'] = job_id
        if detail is not None:
            item['detail'] = detail
        issues.append(item)

    with db() as c:
        _init(c)
        jobs = c.execute('SELECT * FROM ai_compute_jobs WHERE user_id=? AND started_at<? '
                         'AND (finished_at IS NULL OR finished_at>=?) ORDER BY started_at,id',
                         (user_id, b, a)).fetchall()
        existing = c.execute('SELECT id FROM ai_billing_periods WHERE user_id=? AND start_ts<? AND end_ts>?',
                             (user_id, b, a)).fetchone()
        if existing:
            issue('period_already_closed_or_overlapping')
        rated = {r['resource'] for r in c.execute(
            'SELECT DISTINCT resource FROM ai_resource_price_history '
            'WHERE micro_per_unit>0 AND valid_from<? AND (valid_until IS NULL OR valid_until>?)',
            (b, a)) if r['resource'] not in NON_BILLABLE_IO and r['resource'] not in ('disk_gb_hours', 'gpu_slot_seconds_estimated')}
        for job in jobs:
            if job['billable'] == 0:
                continue
            jid = job['id']
            if job['started_at'] < a or job['finished_at'] is None or job['finished_at'] >= b:
                if job['started_at'] < a or job['finished_at'] is not None and job['finished_at'] >= b:
                    issue('boundary_crossing_job', job_id=jid)
            if job['status'] != 'done':
                issue('non_successful_job', job_id=jid, detail=job['status'])
            if job['resource_source'] == 'unmetered':
                issue('unmetered_job', job_id=jid)
            try:
                usage = _validate_usage(json.loads(job['usage_json']))
            except (ValueError, TypeError, json.JSONDecodeError):
                issue('invalid_usage', job_id=jid)
                continue
            source = job['resource_source']
            for resource in sorted(rated):
                if resource not in usage:
                    issue('missing_priced_metric', job_id=jid, detail=resource)
                elif resource == 'gpu_seconds' and source != 'gpu-agent':
                    issue('untrusted_gpu_metric', job_id=jid)
                elif resource == 'cpu_seconds' and source not in ('cgroup', 'worker', 'gpu-agent', 'remote-worker'):
                    issue('untrusted_cpu_metric', job_id=jid)
        disk_paid = bool(c.execute(
            "SELECT 1 FROM ai_resource_price_history WHERE resource='disk_gb_hours' "
            'AND micro_per_unit>0 AND valid_from<? AND (valid_until IS NULL OR valid_until>?) LIMIT 1',
            (b, a)).fetchone())
        storage_root = os.getenv('MTA_AI_USER_STORAGE_ROOT', '')
        if disk_paid and not storage_root:
            issue('storage_root_missing')
        if disk_paid or storage_root:
            samples = c.execute('SELECT sampled_at FROM ai_persistent_storage_samples '
                                'WHERE user_id=? AND sampled_at<=? ORDER BY sampled_at',
                                (user_id, b)).fetchall()
            if not samples or samples[0]['sampled_at'] > a or samples[-1]['sampled_at'] < b:
                issue('storage_coverage_missing')
            elif any(y['sampled_at']-x['sampled_at'] > 26*3600 for x, y in zip(samples, samples[1:])):
                issue('storage_sampling_gap')
        try:
            from .ai_gpu_slot_accounting import priced_period
            priced_period(c,a,b,user_id=user_id)
        except ValueError as exc:
            issue('gpu_slot_coverage_invalid',detail=str(exc))
    return {'user_id': user_id, 'start_ts': a, 'end_ts': b,
            'job_count': len(jobs), 'ready': not issues, 'issues': issues,
            'warning': 'Ledger-only audit; physical GPU metering must be hardware-validated'}


def close_period(user_id, start, end):
    """Create an immutable snapshot under one SQLite write transaction.

    BEGIN IMMEDIATE serializes job finalization, storage sampling and rate
    edits with eligibility checks and cost calculation. No other connection
    may change underlying data between certification and insertion.
    """
    a,b=_window('custom',start=start,end=end)
    with db() as c:
        _init(c)
        c.execute('BEGIN IMMEDIATE')
        existing=c.execute('SELECT * FROM ai_billing_periods WHERE user_id=? AND start_ts=? AND end_ts=? AND currency=?',
                           (user_id,a,b,'EUR')).fetchone()
        if existing:
            return {'id':existing['id'],'total_micro':existing['total_micro'],'already_closed':True}
        mixed_gpu = c.execute("SELECT COUNT(DISTINCT resource) AS n FROM ai_resource_price_history "
            "WHERE resource IN ('gpu_seconds','gpu_slot_seconds_estimated') AND micro_per_unit>0 "
            "AND valid_from<? AND (valid_until IS NULL OR valid_until>?)",(b,a)).fetchone()
        if mixed_gpu['n'] > 1:
            raise ValueError('Measured and estimated GPU tariffs cannot both be active')
        # Account for ALL jobs intersecting the period, including jobs that began
        # before its start. Never let a job crossing a boundary evade verification.
        overlapping = c.execute('SELECT id FROM ai_billing_periods WHERE user_id=? AND start_ts<? AND end_ts>? LIMIT 1',
                                (user_id,b,a)).fetchone()
        if overlapping:
            raise ValueError('Overlapping billing period already closed')
        spanning = c.execute('SELECT id FROM ai_compute_jobs WHERE user_id=? AND started_at<? '
                             'AND started_at<? AND (finished_at IS NULL OR finished_at>=?) AND billable=1 LIMIT 1',
                             (user_id,b,a,a)).fetchone()
        if spanning:
            raise ValueError('A job crossing the billing boundary requires explicit allocation')
        incomplete = c.execute("SELECT id FROM ai_compute_jobs WHERE user_id=? AND started_at>=? AND started_at<? "
                               "AND billable=1 AND (status!='done' OR resource_source='unmetered') LIMIT 1",
                               (user_id,a,b)).fetchone()
        if incomplete:
            raise ValueError('Cannot bill unfinished, failed or unmetered jobs')
        # Billable CPU must be certified per job as well: a GPU agent with
        # GPU-only counters cannot imply a zero CPU charge. Only cgroup or
        # a verified per-process worker meter may certify CPU seconds.
        cpu_rates = c.execute("SELECT 1 FROM ai_resource_price_history WHERE resource='cpu_seconds' "
                              "AND micro_per_unit>0 AND valid_from<? "
                              "AND (valid_until IS NULL OR valid_until>?) LIMIT 1", (b,a)).fetchone()
        if cpu_rates:
            cpu_jobs = c.execute("SELECT id,usage_json,resource_source FROM ai_compute_jobs "
                                 "WHERE user_id=? AND started_at>=? AND started_at<? AND status='done' AND billable=1",
                                 (user_id,a,b)).fetchall()
            for job in cpu_jobs:
                usage = json.loads(job['usage_json'])
                if (job['resource_source'] not in ('cgroup', 'worker', 'gpu-agent', 'remote-worker') or
                    'cpu_seconds' not in usage):
                    raise ValueError('CPU tariff requires verified per-job CPU telemetry')
        # A CPU-only meter cannot certify that a GPU job consumed no GPU.
        # If GPU pricing is enabled, explicit, trusted per-job telemetry is
        # mandatory. Never infer a zero charge from a missing measurement.
        # Require a *separate authenticated measurement for each priced GPU
        # resource. A client-supplied kind is NOT proof that a job was CPU-only.
        # Zero is valid only when supplied explicitly by the trusted GPU agent.
        priced_gpu = [row['resource'] for row in c.execute(
            "SELECT DISTINCT resource FROM ai_resource_price_history WHERE resource IN "
            "('gpu_seconds') AND micro_per_unit>0 "
            "AND valid_from<? AND (valid_until IS NULL OR valid_until>?)",
            (b,a)).fetchall()]
        if priced_gpu:
            gpu_jobs = c.execute("SELECT id,usage_json,resource_source FROM ai_compute_jobs "
                                 "WHERE user_id=? AND started_at>=? AND started_at<? AND status='done' AND billable=1",
                                 (user_id,a,b)).fetchall()
            for job in gpu_jobs:
                usage = json.loads(job['usage_json'])
                if job['resource_source'] != 'gpu-agent' or any(resource not in usage for resource in priced_gpu):
                    raise ValueError('GPU tariff requires verified per-job telemetry for every priced resource')
        # Storage is metered only where it has two bracketing observations.
        # Disabled sampling must never silently become a zero-cost invoice.
        storage_root = os.getenv('MTA_AI_USER_STORAGE_ROOT', '')
        paid_storage = c.execute(
            "SELECT 1 FROM ai_resource_price_history WHERE resource='disk_gb_hours' "
            'AND micro_per_unit>0 AND valid_from<? '
            'AND (valid_until IS NULL OR valid_until>?) LIMIT 1', (b,a)
        ).fetchone()
        if paid_storage and not storage_root:
            raise ValueError('Paid persistent storage requires storage sampling configuration')
        if storage_root:
            samples = c.execute('SELECT sampled_at FROM ai_persistent_storage_samples '
                                'WHERE user_id=? AND sampled_at<=? ORDER BY sampled_at',
                                (user_id,b)).fetchall()
            if not samples or samples[0]['sampled_at']>a or samples[-1]['sampled_at']<b:
                raise ValueError('Incomplete persistent storage measurement coverage')
            if any(y['sampled_at']-x['sampled_at']>26*3600 for x,y in zip(samples,samples[1:])):
                raise ValueError('Storage telemetry gap exceeds maximum accounting interval')
        data=report('custom',user_id=user_id,start=start,end=end,_connection=c)
        if data['unmetered_jobs'] or data['running_jobs']:
            raise ValueError('Cannot bill a period containing unmetered or unfinished jobs')
        try:
            if c.execute('SELECT id FROM ai_billing_periods WHERE user_id=? AND start_ts<? AND end_ts>? LIMIT 1', (user_id,b,a)).fetchone():
                raise ValueError('Overlapping billing period already closed')
            cur=c.execute('INSERT INTO ai_billing_periods(user_id,start_ts,end_ts,currency,total_micro,snapshot_json,created_at) VALUES(?,?,?,?,?,?,?)',
                          (user_id,a,b,'EUR',data['total_micro'],json.dumps(data,sort_keys=True),int(time.time())))
        except sqlite3.IntegrityError:
            row=c.execute('SELECT id,total_micro FROM ai_billing_periods WHERE user_id=? AND start_ts=? AND end_ts=? AND currency=?',
                          (user_id,a,b,'EUR')).fetchone()
            return {'id':row['id'],'total_micro':row['total_micro'],'already_closed':True}
        return {'id':cur.lastrowid,'total_micro':data['total_micro'],'already_closed':False}



def audit_closed_invoices(user_id=None):
    """Read-only integrity audit of immutable billing snapshots.

    Checks saved amounts against *saved* snapshots, never reprices a closed
    invoice using current tariffs. This is an integrity check, not a hardware
    metering attestation. It deliberately detects malformed legacy records.
    """
    findings = []
    with db() as c:
        _init(c)
        query = ('SELECT id,user_id,start_ts,end_ts,currency,total_micro,snapshot_json '
                 'FROM ai_billing_periods')
        params = ()
        if user_id is not None:
            query += ' WHERE user_id=?'
            params = (int(user_id),)
        rows = c.execute(query+' ORDER BY user_id,start_ts,id', params).fetchall()
        previous = {}
        for row in rows:
            invoice_id = row['id']
            def finding(code):
                findings.append({'invoice_id': invoice_id, 'user_id': row['user_id'], 'code': code})
            if row['start_ts'] >= row['end_ts']:
                finding('invalid_interval')
            prior_end = previous.get(row['user_id'])
            if prior_end is not None and row['start_ts'] < prior_end:
                finding('overlapping_closed_period')
            previous[row['user_id']] = max(prior_end or row['end_ts'], row['end_ts'])
            if row['total_micro'] < 0 or row['currency'] != 'EUR':
                finding('invalid_invoice_amount_or_currency')
            try:
                snapshot = json.loads(row['snapshot_json'])
                if not isinstance(snapshot, dict):
                    raise ValueError('snapshot not a dict')
                # Money is stored as integer micro-units. Reject values such as
                # booleans, numeric strings, NaN and floats in archived snapshots.
                total = snapshot.get('total_micro')
                if type(total) is not int or total < 0:
                    raise ValueError('invalid snapshot total')
                if total != row['total_micro']:
                    finding('snapshot_total_mismatch')
                if ((('user_id' in snapshot) and snapshot['user_id'] != row['user_id']) or
                    snapshot.get('start_ts') != row['start_ts'] or
                    snapshot.get('end_ts') != row['end_ts']):
                    finding('snapshot_identity_mismatch')
                rows_data = snapshot.get('rows')
                if not isinstance(rows_data, list):
                    finding('snapshot_rows_missing')
                else:
                    if any(not isinstance(item, dict) or
                           type(item.get('cost_micro')) is not int or
                           item['cost_micro'] < 0 for item in rows_data):
                        finding('invalid_snapshot_rows')
                    elif sum(item['cost_micro'] for item in rows_data) != total:
                        finding('snapshot_rows_total_mismatch')
            except (TypeError, ValueError, json.JSONDecodeError):
                finding('invalid_snapshot_json')
        return {'ready': not findings, 'invoice_count': len(rows), 'issues': findings}


def bills(user_id=None):
    with db() as c:
        _init(c)
        if user_id is None:
            rows = c.execute('SELECT id,user_id,start_ts,end_ts,currency,total_micro,created_at FROM ai_billing_periods ORDER BY id DESC').fetchall()
        else:
            rows = c.execute('SELECT id,user_id,start_ts,end_ts,currency,total_micro,created_at FROM ai_billing_periods WHERE user_id=? ORDER BY id DESC', (user_id,)).fetchall()
        return [dict(x) for x in rows]


def configure_schedule(user_id: int, cadence: str, enabled: bool = True):
    """Per-user UTC billing cadence. Never closes an incomplete current period."""
    if cadence not in ('month', 'week', 'year'):
        raise ValueError('Billing cadence must be week, month or year')
    with db() as c:
        _init(c)
        if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(user_id,)).fetchone():
            raise ValueError('Active user required')
        c.execute('INSERT INTO ai_billing_schedules(user_id,cadence,enabled,created_at) VALUES(?,?,?,?) '
                  'ON CONFLICT(user_id) DO UPDATE SET cadence=excluded.cadence,enabled=excluded.enabled',
                  (user_id,cadence,int(enabled),int(time.time())))

def schedules():
    with db() as c:
        _init(c)
        return [dict(r) for r in c.execute('SELECT user_id,cadence,enabled FROM ai_billing_schedules ORDER BY user_id')]

def run_scheduled_closures(*, at=None):
    """Idempotent closed-period scheduler, run by systemd timer or cron.

    The billing period closes only after the UTC boundary and only if every
    job has been finalized with trusted measurements. No partial invoices.
    """
    now = dt.datetime.fromtimestamp(int(time.time() if at is None else at),dt.timezone.utc).date()
    output=[]
    for spec in schedules():
        if not spec['enabled'] or not user_billing_enabled(spec['user_id']):
            continue
        cadence=spec['cadence']
        if cadence=='month':
            first=now.replace(day=1)
            last=first-dt.timedelta(days=1)
            begin=last.replace(day=1)
        elif cadence=='week':
            first=now-dt.timedelta(days=now.weekday())
            last=first-dt.timedelta(days=1)
            begin=last-dt.timedelta(days=6)
        else:
            begin=dt.date(now.year-1,1,1)
            last=dt.date(now.year-1,12,31)
        try:
            closed=close_period(spec['user_id'],begin.isoformat(),last.isoformat())
            output.append({'user_id':spec['user_id'],'start':begin.isoformat(),
                           'end':last.isoformat(),**closed})
        except ValueError as exc:
            output.append({'user_id':spec['user_id'],'error':str(exc)})
    return output


def finish_job_idempotent(job_id, status, usage=None, *, source='unmetered', finished_at=None):
    """Idempotent retries for durable metering delivery, rejecting conflicts.

    The original finish_job remains a compare-and-set. This wrapper does not
    claim cross-database atomicity with the inference scheduler.
    """
    if finished_at is not None and (isinstance(finished_at, bool) or not isinstance(finished_at, int) or finished_at < 0):
        raise ValueError('Invalid finalization timestamp')
    if status not in ('done', 'failed', 'cancelled'):
        raise ValueError('Invalid final job status')
    values = _validate_usage({} if usage is None else usage)
    if source not in ('unmetered', 'worker', 'cgroup', 'gpu-agent', 'remote-worker'):
        raise ValueError('Invalid metering source')
    if values and source == 'unmetered':
        raise ValueError('Resources require trusted metering source')
    gpu_fields = {'gpu_seconds', 'gpu_energy_joules'}
    if gpu_fields.intersection(values) and source != 'gpu-agent':
        raise ValueError('GPU measurements require trusted gpu-agent source')
    if source == 'gpu-agent' and not gpu_fields.intersection(values):
        raise ValueError('GPU agent must provide an explicit GPU measurement')
    with db() as c:
        _init(c)
        row = c.execute('SELECT status,finished_at,usage_json,resource_source FROM ai_compute_jobs WHERE id=?', (job_id,)).fetchone()
    if row is None:
        raise ValueError('Unknown billing job')
    if row['status'] == 'running':
        try:
            finish_job(job_id, status, values, source=source, finished_at=finished_at)
            return {'job_id': job_id, 'status': status, 'already_finalized': False}
        except ValueError as exc:
            if str(exc) not in ('Job missing or already finalized', 'Job already finalized by another worker'):
                raise
        with db() as c:
            row = c.execute('SELECT status,finished_at,usage_json,resource_source FROM ai_compute_jobs WHERE id=?', (job_id,)).fetchone()
    if (row['status'] != status or row['resource_source'] != source
            or json.loads(row['usage_json']) != values
            or (finished_at is not None and finished_at != row['finished_at'])):
        raise ValueError('Conflicting job finalization retry')
    return {'job_id': job_id, 'status': status, 'already_finalized': True}
