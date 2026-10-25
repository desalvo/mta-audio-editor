import sqlite3

from app.regime_operation_fence import audit_unfenced_metered_jobs, admit, initialize, settle


def test_missing_schema_fails_closed():
    db = sqlite3.connect(':memory:')
    assert audit_unfenced_metered_jobs(db)['verified'] is False


def test_active_legacy_job_blocks_and_enrolled_job_passes():
    db = sqlite3.connect(':memory:')
    initialize(db)
    db.execute('CREATE TABLE ai_compute_jobs(id TEXT PRIMARY KEY,status TEXT NOT NULL)')
    db.execute("INSERT INTO ai_compute_jobs VALUES ('abc','running')")
    db.commit()
    assert audit_unfenced_metered_jobs(db)['unfenced_count'] == 1
    db.execute('BEGIN IMMEDIATE')
    admit(db,'job:ledger:abc','job')
    db.commit()
    assert audit_unfenced_metered_jobs(db)['ready'] is True
    db.execute('BEGIN IMMEDIATE')
    settle(db,'job:ledger:abc')
    db.commit()
    assert audit_unfenced_metered_jobs(db)['unfenced_count'] == 1
    db.execute("UPDATE ai_compute_jobs SET status='completed' WHERE id='abc'")
    assert audit_unfenced_metered_jobs(db)['ready'] is True


def test_terminal_legacy_job_does_not_block():
    db=sqlite3.connect(':memory:')
    initialize(db)
    db.execute('CREATE TABLE ai_compute_jobs(id TEXT PRIMARY KEY,status TEXT NOT NULL)')
    db.execute("INSERT INTO ai_compute_jobs VALUES ('old','completed')")
    assert audit_unfenced_metered_jobs(db)['ready'] is True
