"""Queue crash detection must not confuse a reused PID with its former worker."""
import sqlite3
import time
from app import ai_arranger_runtime as q


def test_migrates_old_database(tmp_path, monkeypatch):
    monkeypatch.setattr(q, '_ROOT', tmp_path)
    db = tmp_path / 'jobs.sqlite3'
    con = sqlite3.connect(db)
    con.execute(q._SCHEMA.replace(',\n runner_identity TEXT', ''))
    con.commit()
    con.close()
    with q._db() as con:
        columns = [column[1] for column in con.execute('PRAGMA table_info(jobs)')]
    assert 'runner_identity' in columns


def test_reused_pid_is_not_a_live_runner(tmp_path, monkeypatch):
    monkeypatch.setattr(q, '_ROOT', tmp_path)
    jid = 'pid-reused'
    with q._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,runner_pid,runner_identity) VALUES(?,?,?,'running',?,?,'running','running',?,?)", (jid, 'p', 'arranger', 1, time.time(), 12345, 'oldboot:1'))
    monkeypatch.setattr(q, '_process_identity', lambda pid: 'newboot:99')
    assert q.get(jid)['state'] == 'interrupted'


def test_current_runner_remains_active(tmp_path, monkeypatch):
    monkeypatch.setattr(q, '_ROOT', tmp_path)
    jid = 'live-runner'
    with q._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,runner_pid,runner_identity) VALUES(?,?,?,'running',?,?,'running','running',?,?)", (jid, 'p', 'arranger', 1, time.time(), 12345, 'current:99'))
    monkeypatch.setattr(q, '_process_identity', lambda pid: 'current:99')
    assert q.get(jid)['state'] == 'running'
