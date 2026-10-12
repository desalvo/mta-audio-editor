"""Energy-cost suggestions must never activate per-user monetary billing."""
import sqlite3
from contextlib import contextmanager

from app import ai_billing, ai_billing_profiles


def test_hardware_suggested_cost_is_distinct_from_billing(tmp_path, monkeypatch):
    database = tmp_path / 'auth.sqlite3'

    @contextmanager
    def isolated_db():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    monkeypatch.setattr(ai_billing, 'db', isolated_db)
    monkeypatch.setattr(ai_billing_profiles, 'local_cpu_model', lambda: 'AMD Ryzen 9 7940HS')
    monkeypatch.setattr(ai_billing_profiles, 'local_gpu_model', lambda: 'AMD Radeon 780M')
    with isolated_db() as connection:
        connection.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, active INTEGER NOT NULL)')
        connection.execute('INSERT INTO users VALUES(1,1)')
    stamp = 1700000000
    job = ai_billing.create_job(1, 'diagnostic_cpu', started_at=stamp)
    ai_billing.finish_job(job, 'done', {'cpu_seconds': 3.0}, source='cgroup', finished_at=stamp + 3)
    result = ai_billing.report('custom', start='2023-11-14', end='2023-11-14', user_id=1)
    assert result['suggested_total_micro'] == 3
    assert result['suggested_cost_is_advisory'] is True
    assert result['total_micro'] == 0
    assert result['billing_enabled_users'] == []
    assert result['hardware_by_job'][job]['cpu_model'] == 'AMD Ryzen 9 7940HS'
