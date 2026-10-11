"""Concurrency regression: each metered completion must stay with its owner."""
from concurrent.futures import ThreadPoolExecutor
import pytest
from app import ai_billing
from app.auth import db, init_auth_db

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as conn:
        for i in range(6):
            conn.execute('INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) '
                         'VALUES(?,?,?,?,?,?,?)', (f'parallel{i}', f'parallel{i}@example.org', 'x', 1, 'user', 1, 1))

def test_parallel_user_jobs_do_not_mix_usage_or_owners():
    with db() as conn:
        users = [r[0] for r in conn.execute("SELECT id FROM users WHERE username LIKE 'parallel%' ORDER BY username")]
    jobs = [ai_billing.create_job(uid, 'whisper', started_at=1760140800) for uid in users]
    def finish(item):
        i, jid = item
        ai_billing.finish_job(jid, 'done', {'cpu_seconds': float(i + 1)}, source='cgroup', finished_at=1760140810)
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(finish, enumerate(jobs)))
    with db() as conn:
        rows = [conn.execute('SELECT user_id,usage_json,status FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone() for jid in jobs]
    import json
    for i, row in enumerate(rows):
        assert row['user_id'] == users[i]
        assert json.loads(row['usage_json'])['cpu_seconds'] == i + 1
        assert row['status'] == 'done'

def test_two_workers_cannot_finalize_same_job_twice():
    with db() as conn:
        uid = conn.execute("SELECT id FROM users WHERE username='parallel0'").fetchone()[0]
    job = ai_billing.create_job(uid, 'whisper', started_at=1760140800)
    def finish(value):
        try:
            ai_billing.finish_job(job, 'done', {'cpu_seconds': value}, source='cgroup', finished_at=1760140810)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(finish, (1.0, 2.0)))
    assert sorted(result) == [False, True]
