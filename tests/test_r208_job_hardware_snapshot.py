"""Advisory hardware identity is frozen for every AI compute job."""
import sqlite3
from contextlib import contextmanager

from app import ai_billing
from app import ai_billing_profiles


def test_snapshot_survives_host_profile_change(tmp_path, monkeypatch):
    database = tmp_path / 'auth.sqlite3'
    @contextmanager
    def isolated_db():
        conn = sqlite3.connect(database)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    monkeypatch.setattr(ai_billing, 'db', isolated_db)
    with isolated_db() as c:
        c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, active INTEGER NOT NULL)')
        c.execute('INSERT INTO users(id,active) VALUES(1,1)')

    monkeypatch.setattr(ai_billing_profiles, 'local_cpu_model', lambda: 'AMD Ryzen 9 7940HS')
    monkeypatch.setattr(ai_billing_profiles, 'local_gpu_model', lambda: 'AMD Radeon 780M')
    first = ai_billing.create_job(1, 'test_gpu', started_at=1700000000)
    snap = ai_billing.job_hardware_snapshot(first)
    assert snap['cpu_model'] == 'AMD Ryzen 9 7940HS'
    assert snap['gpu_model'] == 'AMD Radeon 780M'
    assert snap['gpu_rate_micro'] == 4
    assert snap['cpu_rate_micro'] == 1

    # Simulate LXC migration; the previous job remains priced by its old model.
    monkeypatch.setattr(ai_billing_profiles, 'local_cpu_model', lambda: 'AMD Ryzen AI MAX+ 395')
    monkeypatch.setattr(ai_billing_profiles, 'local_gpu_model', lambda: 'AMD Radeon 8060S')
    second = ai_billing.create_job(1, 'test_gpu', started_at=1700000001)
    assert ai_billing.job_hardware_snapshot(first) == snap
    assert ai_billing.job_hardware_snapshot(second)['gpu_rate_micro'] == 10
    assert ai_billing.user_billing_enabled(1) is False
