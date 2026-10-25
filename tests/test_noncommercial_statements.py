import sqlite3
import pytest
from app.noncommercial_statements import create_statement, list_statements


def db():
    c = sqlite3.connect(':memory:', isolation_level=None)
    c.execute('''CREATE TABLE ai_compute_jobs (
       id INTEGER, user_id INTEGER, started_at INTEGER, status TEXT,
       usage_json TEXT, resource_source TEXT, billable INTEGER)''')
    c.execute('''INSERT INTO ai_compute_jobs VALUES
       (1,1,100,'completed','{"cpu_seconds":1,"gpu_seconds":2}','gpu-agent',1),
       (2,2,101,'completed','{"cpu_seconds":2,"gpu_seconds":1}','gpu-agent',1)''')
    return c


def test_immutable_snapshot_and_no_double_booking():
    c = db()
    r = create_statement(c,start=100,end=200,documented_cost_cents=101)
    assert r['total_draft_cents'] == 101
    assert r['posting_enabled'] is False
    assert list_statements(c)[0]['sha256']==r['sha256']
    with pytest.raises(ValueError, match='Overlapping'):
        create_statement(c,start=150,end=250,documented_cost_cents=100)
    assert len(list_statements(c)) == 1


def test_rolls_back_invalid_measurement():
    c = db()
    c.execute("UPDATE ai_compute_jobs SET usage_json='{}',resource_source=NULL WHERE id=2")
    with pytest.raises(ValueError):
        create_statement(c,start=100,end=200,documented_cost_cents=100)
    assert list_statements(c)==[]


def test_detect_tampering():
    c=db()
    create_statement(c,start=100,end=200,documented_cost_cents=100)
    with pytest.raises(__import__('sqlite3').IntegrityError):
        c.execute("UPDATE nc_period_statements SET statement_json='{}'")
    # Verify the hash check still detects database files tampered outside normal writes.
    c.execute('DROP TRIGGER nc_statement_no_update')
    c.execute("UPDATE nc_period_statements SET statement_json='{}'")
    with pytest.raises(ValueError, match='Tampered'):
        list_statements(c)
