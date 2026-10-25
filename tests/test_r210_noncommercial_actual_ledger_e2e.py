"""Real ledger completion -> frozen NC statement -> private bilingual export."""
import sqlite3
import pytest
from app import auth,ai_billing
from app.noncommercial_statements import create_statement,export_statement_csv,user_statement_csv


def test_completed_actual_job_closes_period_and_exports_both_languages(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path));monkeypatch.setattr(auth,'DATA_ROOT',tmp_path)
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','a-secure-test-password')
    auth.init_auth_db()
    with auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) VALUES('nc-user','nc@example.test','unused','user',1,1,1,1)")
        uid=c.execute("SELECT id FROM users WHERE username='nc-user'").fetchone()[0]
    job=ai_billing.create_job(uid,'whisper',started_at=200)
    ai_billing.finish_job(job,'done',{'cpu_seconds':2},source='worker',finished_at=202)
    with auth.db() as c:
        result=create_statement(c,start=100,end=300,documented_cost_cents=99)
        assert result['jobs_count']==1 and result['contribution_cents']=={str(uid):99}
        assert not result['payments_collected']
        assert 'account_id' in export_statement_csv(c,start=100,end=300)['content']
        personal=user_statement_csv(c,str(uid),start=100,end=300,language='it')
        assert personal['content'].startswith('id_account,millisecondi_misurati')
        with pytest.raises(ValueError):user_statement_csv(c,str(uid+1),start=100,end=300)
        with pytest.raises(sqlite3.IntegrityError):c.execute("UPDATE ai_compute_jobs SET usage_json='{}' WHERE id=?",(job,))
    with pytest.raises(sqlite3.IntegrityError):ai_billing.create_job(uid,'whisper',started_at=250)
