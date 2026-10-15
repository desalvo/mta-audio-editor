import sqlite3
import pytest
from app import ai_metering_bridge as bridge


def test_durable_sink_binding_and_replay(monkeypatch, tmp_path):
    db = tmp_path / 'test.sqlite'
    def connect():
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        return conn
    # This test replaces queue._db, so initialize its isolated DB schema as
    # the real queue._db does before metering updates the durable jobs row.
    with connect() as con:
        con.execute(bridge.queue._SCHEMA)
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message) VALUES(?,?,?,?,?,?,?,?)",
                    ('local1', 'project1', 'arranger', 'running', 1, 0.0, 'inference', ''))
    monkeypatch.setattr(bridge.queue, '_db', connect)
    monkeypatch.setattr(bridge, '_identity', lambda job: (1, 'arranger'))
    sink = bridge.durable_remote_sink('local1', request_id='req1', worker_id='worker1')
    envelope = {'job_id': 'remote1', 'request_id': 'req1', 'worker_id': 'worker1'}
    assert sink(envelope, {'cpu_seconds': 1.5}) is True
    assert sink(envelope, {'cpu_seconds': 1.5}) is False
    with pytest.raises(ValueError, match='Conflicting'):
        sink({**envelope, 'job_id': 'remote2'}, {'cpu_seconds': 1.5})
    with pytest.raises(ValueError, match='Conflicting'):
        sink(envelope, {'cpu_seconds': 2.0})
    with pytest.raises(ValueError, match='binding'):
        sink({**envelope, 'worker_id': 'worker2'}, {'cpu_seconds': 1.5})
    with pytest.raises(ValueError, match='GPU|CPU'):
        sink(envelope, {'cpu_seconds': 1.5, 'gpu_seconds': 1})


@pytest.mark.parametrize('bad', ['', 'bad value', '../bad', None, 0])
def test_reject_invalid_binding_ids(monkeypatch, bad):
    monkeypatch.setattr(bridge, '_identity', lambda job: (1, 'arranger'))
    with pytest.raises(ValueError):
        bridge.durable_remote_sink('local', request_id=bad, worker_id='worker')
