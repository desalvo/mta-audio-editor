"""Regression checks for explicit SQL query variants and per-user isolation."""
import pytest

from app import ai_access, ai_billing
from app.auth import db, init_auth_db


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    init_auth_db()
    with db() as conn:
        for name in ('alpha', 'beta'):
            conn.execute('INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) '
                         'VALUES(?,?,?,?,?,?,?)', (name, name + '@example.test', 'x', 1, 'user', 1, 1))


def test_access_token_and_event_scoping():
    with db() as conn:
        users = [row[0] for row in conn.execute('SELECT id FROM users ORDER BY id').fetchall()]
    token_ids = [ai_access.issue(uid, 'test')['id'] for uid in users]
    ai_access.usage(token_ids[0], users[0], '/api/ai-jobs', 100, 200)
    assert {row['user_id'] for row in ai_access.list_tokens()} == set(users)
    assert [row['id'] for row in ai_access.list_tokens(users[1])] == [token_ids[1]]
    assert ai_access.summary(users[1]) == []
    assert len(ai_access.summary(users[0])) == 1


def test_invoice_and_tariff_filters():
    with db() as conn:
        users = [row[0] for row in conn.execute('SELECT id FROM users ORDER BY id').fetchall()]
    ai_billing.close_period(users[0], '2025-05-01', '2025-05-31')
    assert len(ai_billing.bills()) == 1
    assert len(ai_billing.bills(users[0])) == 1
    assert ai_billing.bills(users[1]) == []
    assert all(row['resource'] == 'cpu_seconds' for row in ai_billing.tariff_history('cpu_seconds'))
