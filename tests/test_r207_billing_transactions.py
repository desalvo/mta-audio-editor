"""Transaction guarantees for the durable AI ledger."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.auth import db, init_auth_db
from app import ai_billing


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as conn:
        conn.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) "
                     "VALUES('ledger','ledger@example.org','x',1,'user',1,1)")


def test_connection_rollback_on_error():
    with pytest.raises(RuntimeError, match='abort'):
        with db() as conn:
            conn.execute("UPDATE users SET email='invalid@example.org' WHERE username='ledger'")
            raise RuntimeError('abort')
    with db() as conn:
        assert conn.execute("SELECT email FROM users WHERE username='ledger'").fetchone()[0] == 'ledger@example.org'


def test_rejected_tariff_edit_does_not_change_history():
    ai_billing.set_price('cpu_seconds', 100, valid_from='2025-01-01')
    ai_billing.set_price('cpu_seconds', 200, valid_from='2025-03-01')
    before = ai_billing.tariff_history('cpu_seconds')
    with pytest.raises(ValueError, match='Overlapping tariff'):
        ai_billing.set_price('cpu_seconds', 150, valid_from='2025-02-01', valid_until='2025-04-01')
    assert ai_billing.tariff_history('cpu_seconds') == before


def test_concurrent_storage_samples_do_not_cross_closed_period():
    with db() as conn:
        uid = conn.execute("SELECT id FROM users WHERE username='ledger'").fetchone()[0]
    stamp = 1746100800
    barrier = Barrier(2)

    def sample():
        barrier.wait()
        try:
            ai_billing.record_persistent_storage(uid, 42, sampled_at=stamp)
            return 'stored'
        except ValueError:
            return 'closed'

    def close():
        barrier.wait()
        return ai_billing.close_period(uid, '2025-05-01', '2025-05-31')

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_sample = pool.submit(sample)
        future_close = pool.submit(close)
        result = future_sample.result()
        future_close.result()
    assert result in {'stored', 'closed'}
    with db() as conn:
        rows = conn.execute('SELECT bytes_used FROM ai_persistent_storage_samples WHERE user_id=?', (uid,)).fetchall()
    assert not rows if result == 'closed' else len(rows) == 1
    with pytest.raises(ValueError, match='closed billing interval'):
        ai_billing.record_persistent_storage(uid, 43, sampled_at=stamp)
