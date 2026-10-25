"""Database-enforced immutability for finalized noncommercial metering periods.

Installed on the same SQLite connection used to close a period. Applies to
all writers, including legacy paths that bypass the HTTP/API layer.
"""
from __future__ import annotations

import sqlite3


TRIGGERS = {
    'nc_closed_period_no_insert': '''CREATE TRIGGER IF NOT EXISTS nc_closed_period_no_insert
        BEFORE INSERT ON ai_compute_jobs WHEN EXISTS (
          SELECT 1 FROM nc_period_statements p
          WHERE NEW.started_at >= p.period_start AND NEW.started_at < p.period_end)
        BEGIN SELECT RAISE(ABORT, 'Closed noncommercial period: job insertion denied'); END''',
    'nc_closed_period_no_update': '''CREATE TRIGGER IF NOT EXISTS nc_closed_period_no_update
        BEFORE UPDATE ON ai_compute_jobs WHEN EXISTS (
          SELECT 1 FROM nc_period_statements p
          WHERE (OLD.started_at >= p.period_start AND OLD.started_at < p.period_end)
             OR (NEW.started_at >= p.period_start AND NEW.started_at < p.period_end))
        BEGIN SELECT RAISE(ABORT, 'Closed noncommercial period: job update denied'); END''',
    'nc_statement_no_update': '''CREATE TRIGGER IF NOT EXISTS nc_statement_no_update
        BEFORE UPDATE ON nc_period_statements
        BEGIN SELECT RAISE(ABORT, 'Immutable noncommercial statement'); END''',
    'nc_statement_no_delete': '''CREATE TRIGGER IF NOT EXISTS nc_statement_no_delete
        BEFORE DELETE ON nc_period_statements
        BEGIN SELECT RAISE(ABORT, 'Immutable noncommercial statement'); END''',
    'nc_closed_period_no_delete': '''CREATE TRIGGER IF NOT EXISTS nc_closed_period_no_delete
        BEFORE DELETE ON ai_compute_jobs WHEN EXISTS (
          SELECT 1 FROM nc_period_statements p
          WHERE OLD.started_at >= p.period_start AND OLD.started_at < p.period_end)
        AND mta_nc_erasure('ai_compute_jobs',OLD.id)=0
        BEGIN SELECT RAISE(ABORT, 'Closed noncommercial period: job deletion denied'); END''',
}


def install_closed_period_guards(connection: sqlite3.Connection) -> None:
    """Install guards inside caller-owned transaction, fail closed on absent schema."""
    if not connection.in_transaction:
        raise ValueError('Write transaction required for closed-period guards')
    try:
        connection.execute("SELECT mta_nc_erasure('','')")
    except sqlite3.OperationalError:
        connection.create_function('mta_nc_erasure',2,lambda table,key:0)
    for table in ('ai_compute_jobs', 'nc_period_statements'):
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is None:
            raise ValueError(f'Required accounting table missing: {table}')
    columns = {r[1] for r in connection.execute('PRAGMA table_info(ai_compute_jobs)')}
    if 'started_at' not in columns:
        raise ValueError('Missing ledger timestamp')
    # Upgrade the legacy delete guard atomically; ordinary writers stay denied.
    connection.execute('DROP TRIGGER IF EXISTS nc_closed_period_no_delete')
    for sql in TRIGGERS.values():
        connection.execute(sql)
