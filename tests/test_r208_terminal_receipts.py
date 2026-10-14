"""Atomic final outcomes, no duplicate queue-level terminal receipts."""
import time
from app import ai_arranger_runtime as q


def _await(jid, state):
    for _ in range(150):
        if q.get(jid)['state'] == state:
            return
        time.sleep(.02)
    assert q.get(jid)['state'] == state


def test_finished_job_has_single_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(q, '_ROOT', tmp_path)
    q.configure(1)
    jid = q.start('p', 'test-done', lambda _: None)[1]['job_id']
    _await(jid, 'completed')
    one = q.terminal_receipt(jid)
    assert one['state'] == 'completed'
    with q._db() as con:
        assert con.execute('SELECT COUNT(*) FROM terminal_receipts WHERE job_id=?', (jid,)).fetchone()[0] == 1
    assert q.terminal_receipt(jid) == one


def test_cancelled_queue_job_receipted_once(tmp_path, monkeypatch):
    monkeypatch.setattr(q, '_ROOT', tmp_path)
    q.configure(1)
    with q._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message) VALUES(?,?,?,'blocked',?,?,?,?)", ('job-fixed', 'p', 'absent', 1, time.time(), 'blocked', 'waiting'))
    assert q.cancel('job-fixed')['state'] == 'cancelled'
    receipt = q.terminal_receipt('job-fixed')
    assert receipt['state'] == 'cancelled'
    assert q.cancel('job-fixed')['state'] == 'cancelled'
    assert q.terminal_receipt('job-fixed') == receipt
