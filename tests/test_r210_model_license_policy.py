import pytest
from app import model_license_policy as policy,auth,ai_billing


@pytest.fixture
def rights(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path)
    auth.init_auth_db()
    with auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('license','license@example.org','unused',1,'user',1,1)")
        return c.execute("SELECT id FROM users WHERE username='license'").fetchone()[0]


def reviewed(mode='free_only'):
    return {'mode':mode,'acknowledge_responsibility':True,'evidence_url':'https://example.org/permission',
        'reason':'Operator reviewed original license and separately authorized this use','free_access_confirmed':True,'confirm_risk_twice':True,'authorization_basis':'written_permission'}


def test_reimbursement_is_not_an_automatic_license_exception(rights):
    for model in ('madmom','diffsinger-qixuan','diffsinger-nishiren','diffsinger-spore','chordformer','audio-separator-weights','drumsep-weights'):
        with pytest.raises(policy.LicenseDenied):policy.evaluate_model(model)
    assert policy.evaluate_model('oddvoices').billable
    assert policy.evaluate_model('sam-audio').billable
    assert policy.evaluate_model('btc-hcqt').billable


def test_review_requires_permission_and_free_access_acknowledgement(rights):
    for changes in ({'acknowledge_responsibility':False},{'evidence_url':'http://example.org'}, {'free_access_confirmed':False}):
        with pytest.raises(ValueError):policy.configure('madmom',{**reviewed(),**changes},rights)
    with pytest.raises(ValueError,match='paid inference'):policy.configure('diffsinger-qixuan',reviewed('cost_recovery'),rights)
    policy.configure('madmom',reviewed(),rights)
    assert not policy.evaluate_model('madmom').billable


def test_free_resources_remain_accounted_without_billing_or_quota_use(rights):
    ai_billing.set_price('cpu_seconds',1000000,valid_from='2025-01-01')
    ai_billing.set_user_billing_enabled(rights,True)
    jid=ai_billing.create_job(rights,'whisper',billing_exemption_reason='license:fixture')
    ai_billing.finish_job(jid,'done',{'cpu_seconds':20},source='worker')
    with auth.db() as c:
        row=c.execute('SELECT * FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone()
        assert row['billable']==0 and '20' in row['usage_json']
        from app.resource_accounts import _used
        assert _used(c,rights,0,9999999999)['cpu_seconds']==0


def test_license_snapshot_is_idempotent_but_not_mutable(rights):
    jid=ai_billing.create_job(rights,'whisper');decision=policy.evaluate_model('whisper')
    policy.record_job(jid,decision);policy.record_job(jid,decision)
    policy.configure('whisper',reviewed(),rights)
    with pytest.raises(policy.LicenseDenied,match='changed'):policy.record_job(jid,policy.evaluate_model('whisper'))
