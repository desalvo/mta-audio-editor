import pytest
from app import ai_billing
from app.auth import db, init_auth_db


@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('owner','owner@example.org','x',1,'user',1,1)")


def uid():
    with db() as con:
        return con.execute('SELECT id FROM users WHERE username=?', ('owner',)).fetchone()[0]


def test_recovery_dry_run_does_not_change_running_jobs():
    job = ai_billing.create_job(uid(), 'whisper', started_at=100)
    report = ai_billing.recover_stale_jobs(now=5000, older_than_seconds=3600)
    assert [j['job_id'] for j in report['candidates']] == [job]
    assert report['recovered_job_ids'] == []
    with db() as con:
        assert con.execute('SELECT status FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()[0] == 'running'


def test_recovery_marks_only_stale_running_jobs_unmetered():
    old = ai_billing.create_job(uid(), 'whisper', started_at=100)
    recent = ai_billing.create_job(uid(), 'demucs', started_at=4500)
    completed = ai_billing.create_job(uid(), 'chords', started_at=120)
    ai_billing.finish_job(completed, 'done', {'cpu_seconds': 3}, source='worker', finished_at=130)
    report = ai_billing.recover_stale_jobs(now=5000, older_than_seconds=3600, dry_run=False)
    assert report['recovered_job_ids'] == [old]
    assert ai_billing.recover_stale_jobs(now=5000, older_than_seconds=3600, dry_run=False)['recovered_job_ids'] == []
    with db() as con:
        old_row = con.execute('SELECT status,usage_json,resource_source FROM ai_compute_jobs WHERE id=?', (old,)).fetchone()
        assert tuple(old_row) == ('failed', '{}', 'unmetered')
        assert con.execute('SELECT status FROM ai_compute_jobs WHERE id=?', (recent,)).fetchone()[0] == 'running'
        assert con.execute('SELECT status FROM ai_compute_jobs WHERE id=?', (completed,)).fetchone()[0] == 'done'
    with pytest.raises(ValueError, match='already finalized'):
        ai_billing.finish_job(old, 'done', {'cpu_seconds': 12}, source='worker', finished_at=5001)


@pytest.mark.parametrize('threshold', [0, 1, 3599, -1, True, 3600.5])
def test_recovery_rejects_unsafe_threshold(threshold):
    with pytest.raises(ValueError):
        ai_billing.recover_stale_jobs(older_than_seconds=threshold)

@pytest.mark.parametrize('claim_state', ['running', 'finished'])
def test_recovery_never_bypasses_persisted_worker_claim(claim_state):
    from app.regime_worker_claims import claim, finish
    job = ai_billing.create_job(uid(), 'whisper', started_at=100)
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        claim(con, job, worker_id='remote-1', token='verified-token')
        if claim_state == 'finished':
            finish(con, 'job:ledger:' + job, worker_id='remote-1', token='verified-token')
    report = ai_billing.recover_stale_jobs(now=5000, older_than_seconds=3600, dry_run=False)
    assert report['recovered_job_ids'] == []
    assert report['blocked_jobs'] == [{'job_id': job, 'reason': 'worker_claim_requires_audited_resolution'}]
    with db() as con:
        assert con.execute('SELECT status FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()[0] == 'running'
