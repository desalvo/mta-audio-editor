"""Paid persistent storage needs actual user-scoped samples, not missing data."""
import datetime as dt
import pytest
from app import ai_billing
from app.auth import db, init_auth_db

@pytest.fixture(autouse=True)
def account(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('MTA_AI_USER_STORAGE_ROOT', raising=False)
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('storage','storage@example.org','test',1,'user',1,1)")

def uid():
    with db() as c:
        return c.execute("SELECT id FROM users WHERE username='storage'").fetchone()[0]

def stamp(value):
    return int(dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp())

def test_paid_storage_requires_sampler_configuration():
    ai_billing.set_price('disk_gb_hours', 100, valid_from='2025-01-01')
    with pytest.raises(ValueError, match='storage sampling'):
        ai_billing.close_period(uid(), '2025-05-01', '2025-05-02')

def test_paid_storage_requires_samples_even_if_storage_root_configured(tmp_path, monkeypatch):
    ai_billing.set_price('disk_gb_hours', 100, valid_from='2025-01-01')
    root=tmp_path/'storage'; root.mkdir()
    monkeypatch.setenv('MTA_AI_USER_STORAGE_ROOT', str(root))
    with pytest.raises(ValueError, match='Incomplete persistent storage'):
        ai_billing.close_period(uid(), '2025-05-01', '2025-05-02')

def test_free_storage_does_not_force_sampling():
    ai_billing.set_price('disk_gb_hours', 0, valid_from='2025-01-01')
    result=ai_billing.close_period(uid(), '2025-05-01', '2025-05-02')
    assert result['total_micro'] == 0
