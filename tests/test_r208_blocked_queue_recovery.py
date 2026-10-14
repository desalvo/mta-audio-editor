"""Durable queue must not deadlock when an optional adapter is unavailable."""
import threading
import time
from app import ai_arranger_runtime as q


def _wait_for(jid, state):
    for _ in range(100):
        if q.get(jid)['state'] == state:
            return
        time.sleep(.03)
    assert q.get(jid)['state'] == state


def test_missing_adapter_does_not_starve_following_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(q, '_ROOT', tmp_path)
    q.configure(1)
    gate = threading.Event()
    entered = threading.Event()
    first = q.start('p', 'blocking', lambda _: (entered.set(), gate.wait(4)))[1]
    assert entered.wait(3)
    missing = q.start('p', 'optional-adapter', lambda _: None, payload={'v': 1})[1]
    with q._MUTEX:
        q._LOCAL[missing['job_id']].set()
    _wait_for(missing['job_id'], 'queued')
    for _ in range(100):
        with q._MUTEX:
            if missing['job_id'] not in q._LOCAL:
                break
        time.sleep(.02)
    q.recover_queued()
    assert q.get(missing['job_id'])['state'] == 'blocked'
    latter = q.start('p', 'ready', lambda _: None)[1]
    gate.set()
    _wait_for(first['job_id'], 'completed')
    _wait_for(latter['job_id'], 'completed')
    assert q.cancel(missing['job_id'])['state'] == 'cancelled'


def test_blocked_job_restores_once_adapter_available(tmp_path, monkeypatch):
    monkeypatch.setattr(q, '_ROOT', tmp_path)
    jid = 'durable-one'
    with q._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,payload_json) VALUES(?,?,?,'blocked',?,?,'blocked','waiting',?)", (jid, 'p', 'test-restorer-blocked', 1, time.time(), '{"v":1}'))
    calls = []
    q.register_restorer('test-restorer-blocked', lambda pid, payload, job_id: lambda path, stop: calls.append(job_id))
    try:
        assert q.recover_queued() == 1
        assert q.recover_queued() == 0
        _wait_for(jid, 'completed')
        assert calls == [jid]
    finally:
        q._RESTORERS.pop('test-restorer-blocked', None)
