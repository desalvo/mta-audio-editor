"""Durable billing delivery may retry, never mutate the original measurement."""
import pytest
from app.auth import db, init_auth_db
from app import ai_billing

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('tester','tester@example.org','x',1,'user',1,1)")

def test_same_delivery_is_idempotent():
    with db() as c:
        uid = c.execute("SELECT id FROM users WHERE username='tester'").fetchone()[0]
    jid = ai_billing.create_job(uid, 'whisper', started_at=1748736000)
    kw = dict(source='cgroup', finished_at=1748736004)
    assert ai_billing.finish_job_idempotent(jid, 'done', {'cpu_seconds':3}, **kw)['already_finalized'] is False
    assert ai_billing.finish_job_idempotent(jid, 'done', {'cpu_seconds':3}, **kw)['already_finalized'] is True
    with pytest.raises(ValueError, match='Conflicting'):
        ai_billing.finish_job_idempotent(jid, 'done', {'cpu_seconds':4}, **kw)
    with pytest.raises(ValueError, match='Conflicting'):
        ai_billing.finish_job_idempotent(jid, 'failed', {'cpu_seconds':3}, **kw)


def test_concurrent_identical_deliveries_finalize_once():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    with db() as c:
        uid = c.execute("SELECT id FROM users WHERE username='tester'").fetchone()[0]
    jid = ai_billing.create_job(uid, 'whisper', started_at=1748736000)
    barrier = Barrier(4)
    def deliver(_):
        barrier.wait()
        return ai_billing.finish_job_idempotent(jid, 'done', {'cpu_seconds': 3},
                                                source='cgroup', finished_at=1748736004)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(deliver, range(4)))
    assert sum(not result['already_finalized'] for result in results) == 1
    assert sum(result['already_finalized'] for result in results) == 3
    with db() as c:
        assert c.execute('SELECT COUNT(*) FROM ai_compute_jobs WHERE id=? AND status=?',
                         (jid, 'done')).fetchone()[0] == 1


def test_nonexistent_delivery_rejected():
    with pytest.raises(ValueError, match='Unknown billing job'):
        ai_billing.finish_job_idempotent('missing', 'done')


def test_idempotent_retry_after_period_close():
    with db() as c:
        uid = c.execute("SELECT id FROM users WHERE username='tester'").fetchone()[0]
    jid = ai_billing.create_job(uid, 'whisper', started_at=1748736000)
    kwargs = {'source': 'cgroup', 'finished_at': 1748736004}
    assert not ai_billing.finish_job_idempotent(jid, 'done', {'cpu_seconds': 3}, **kwargs)['already_finalized']
    ai_billing.close_period(uid, '2025-06-01', '2025-06-30')
    assert ai_billing.finish_job_idempotent(jid, 'done', {'cpu_seconds': 3}, **kwargs)['already_finalized']
    with pytest.raises(ValueError, match='Conflicting'):
        ai_billing.finish_job_idempotent(jid, 'done', {'cpu_seconds': 4}, **kwargs)


@pytest.mark.parametrize('timestamp', [True, 1748736004.5, -1, '1748736004'])
def test_invalid_delivery_timestamp_is_rejected(timestamp):
    with pytest.raises(ValueError, match='Invalid finalization timestamp'):
        ai_billing.finish_job_idempotent('missing', 'done', finished_at=timestamp)
