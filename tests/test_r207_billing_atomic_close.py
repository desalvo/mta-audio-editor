"""Closure is idempotent across threads and immutable against late job writes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from app.auth import db, init_auth_db
from app import ai_billing

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('tester','tester@example.org','x',1,'user',1,1)")

def user():
    with db() as c:
        return c.execute("SELECT id FROM users WHERE username='tester'").fetchone()[0]

def test_concurrent_close_single_snapshot():
    uid = user()
    barrier=Barrier(4)
    def close():
        barrier.wait()
        return ai_billing.close_period(uid,'2025-05-01','2025-05-31')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _: close(), range(4)))
    assert len({x['id'] for x in results}) == 1
    assert sum(not x['already_closed'] for x in results) == 1
    assert len(ai_billing.bills(uid)) == 1

def test_closed_period_rejects_late_job_insertion():
    uid=user()
    ai_billing.close_period(uid,'2025-05-01','2025-05-31')
    with pytest.raises(ValueError, match='closed billing interval'):
        ai_billing.create_job(uid,'whisper',started_at=1746100800)

def test_period_before_job_is_allowed():
    uid=user()
    ai_billing.close_period(uid,'2025-05-01','2025-05-31')
    job=ai_billing.create_job(uid,'whisper',started_at=1748736000)
    ai_billing.finish_job(job,'done',{'cpu_seconds':3},source='cgroup',finished_at=1748736004)
