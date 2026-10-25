"""Integration of the real job ledger with noncommercial preview, no money mutation."""
import json
import sqlite3
import pytest
from app.noncommercial_allocation import preview_from_metered_jobs


def ledger():
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE ai_compute_jobs (id TEXT,user_id INTEGER, started_at INTEGER, status TEXT, usage_json TEXT, resource_source TEXT, billable INTEGER, accounting_excluded INTEGER)')
    return c


def test_preview_conserves_cost_without_charging():
    c = ledger()
    c.executemany('INSERT INTO ai_compute_jobs VALUES (?,?,?,?,?,?,?,?)', [
        ('a', 1, 200, 'completed', json.dumps({'cpu_seconds': 1}), 'worker', 1, 0),
        ('b', 2, 200, 'completed', json.dumps({'gpu_seconds': 3}), 'gpu-agent', 1, 0),
        ('c', 3, 200, 'completed', '{}', 'worker', 0, 0),
        ('d', 3, 200, 'completed', '{}', 'worker', 1, 1),
    ])
    before = c.total_changes
    r = preview_from_metered_jobs(c, start=100, end=300, documented_cost_cents=100, recovered_cents=20)
    assert r['contribution_cents'] == {'1': 20, '2': 60}
    assert r['total_draft_cents'] == 80
    assert r['jobs_count'] == 2
    assert r['posting_enabled'] is False
    assert c.total_changes == before


@pytest.mark.parametrize('usage,source,status', [
    ('{}', 'unmetered', 'completed'),
    ('{}', 'worker', 'running'),
    ('{"cpu_seconds": -1}', 'worker', 'completed'),
    ('{"gpu_seconds": NaN}', 'worker', 'completed'),
    ('bad json', 'worker', 'completed'),
])
def test_incomplete_accounting_fails_closed(usage, source, status):
    c = ledger()
    c.execute('INSERT INTO ai_compute_jobs VALUES (?,?,?,?,?,?,?,?)',
              ('x', 1, 200, status, usage, source, 1, 0))
    with pytest.raises(ValueError):
        preview_from_metered_jobs(c, start=100, end=300, documented_cost_cents=10)


def test_missing_ledger_is_blocker():
    with pytest.raises(ValueError):
        preview_from_metered_jobs(sqlite3.connect(':memory:'), start=1, end=2,
                                  documented_cost_cents=100)
