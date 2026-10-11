"""Regression: GPU energy is recorded, never billed in r207."""
from app import ai_billing
from app.auth import db, init_auth_db

def test_energy_never_charged_even_if_legacy_tariff_exists(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('MTA_AI_USER_STORAGE_ROOT', raising=False)
    init_auth_db()
    with db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('energyuser','e@example.org','x',1,'user',1,1)")
        user_id = c.execute("SELECT id FROM users WHERE username='energyuser'").fetchone()[0]
    ai_billing.set_price('gpu_seconds', 200, valid_from='2025-01-01')
    ai_billing.set_price('gpu_energy_joules', 9000, valid_from='2025-01-01')
    job = ai_billing.create_job(user_id, 'ace', started_at=1760140800)
    ai_billing.finish_job(job, 'done', {'gpu_seconds':3, 'gpu_energy_joules':999}, source='gpu-agent', finished_at=1760140810)
    result = ai_billing.close_period(user_id, '2025-10-11', '2025-10-11')
    assert result['total_micro'] == 600
    report = ai_billing.report('day',user_id=user_id,anchor='2025-10-11')
    assert sum(x['resources'].get('gpu_energy_joules',0) for x in report['rows']) == 999
