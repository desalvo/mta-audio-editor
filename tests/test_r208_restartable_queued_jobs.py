"""Queued durable work can resume without replaying external running effects."""
import sqlite3
import threading
import time
from app import ai_arranger_runtime as queue


def test_recover_queued_without_duplicate_work(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    queue.configure(1)
    started = threading.Event()
    release = threading.Event()
    first = queue.start('a', 'test-block', lambda _: (started.set(), release.wait(5)))[1]
    assert started.wait(4)
    second = queue.start('b', 'test-resumable', lambda _: None,
                         payload={'schema_version': 1, 'request': {'input': 2}})[1]
    jid = second['job_id']
    assert queue.get(jid)['state'] == 'queued'
    # Emulate process loss for a still-unstarted job, not a running job.
    with queue._MUTEX:
        queue._LOCAL[jid].set()
    time.sleep(.1)
    calls = []
    queue.register_restorer('test-resumable', lambda pid, payload, job_id:
        lambda progress, cancel: calls.append((pid, payload, job_id)))
    try:
        assert queue.recover_queued() == 1
        assert queue.recover_queued() == 0
        release.set()
        for _ in range(100):
            if queue.get(jid)['state'] == 'completed':
                break
            time.sleep(.05)
        assert queue.get(jid)['state'] == 'completed'
        assert calls == [('b', {'schema_version': 1, 'request': {'input': 2}}, jid)]
    finally:
        release.set()
        queue._RESTORERS.pop('test-resumable', None)


def test_running_orphan_is_not_replayed(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,runner_pid,runner_identity,payload_json) VALUES(?,?,?,'running',?,?,?, ?,?,?,?)",
                    ('orphan', 'p', 'arranger', 1, time.time(), 'inference', 'running', 99999999, 'otherboot:1', '{"request":{}}'))
    assert queue.recover_queued() == 0
    assert queue.get('orphan')['state'] == 'interrupted'
