import sqlite3

import pytest

from app.noncommercial_period_guard import install_closed_period_guards


def database():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE ai_compute_jobs (id TEXT PRIMARY KEY, started_at INTEGER NOT NULL, status TEXT)')
    db.execute('CREATE TABLE nc_period_statements (period_start INTEGER, period_end INTEGER)')
    db.commit()
    db.execute('BEGIN IMMEDIATE')
    install_closed_period_guards(db)
    db.execute('INSERT INTO ai_compute_jobs VALUES (?,?,?)', ('earlier', 50, 'completed'))
    db.execute('INSERT INTO ai_compute_jobs VALUES (?,?,?)', ('later', 250, 'completed'))
    db.execute('INSERT INTO nc_period_statements VALUES (100,200)')
    db.commit()
    return db


def test_closed_period_blocks_late_job():
    db = database()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute('INSERT INTO ai_compute_jobs VALUES (?,?,?)', ('late', 150, 'completed'))
    db.rollback()


def test_closed_period_blocks_move_in_and_out():
    db = database()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute('UPDATE ai_compute_jobs SET started_at=150 WHERE id="earlier"')
    db.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute('DELETE FROM nc_period_statements')
    db.rollback()


def test_other_period_writes_allowed():
    db = database()
    db.execute('INSERT INTO ai_compute_jobs VALUES (?,?,?)', ('new', 300, 'running'))
    db.execute('UPDATE ai_compute_jobs SET status="completed" WHERE id="new"')
    db.commit()


def test_transaction_required():
    db = sqlite3.connect(':memory:')
    with pytest.raises(ValueError):
        install_closed_period_guards(db)


def test_statement_cannot_be_modified():
    db = database()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute('UPDATE nc_period_statements SET period_end=300')
    db.rollback()
