"""Authorize generated test data only; production defaults stay fail-closed."""
def authorize_fixture(monkeypatch,tmp_path,model):
    from app import model_license_policy as policy
    monkeypatch.setattr(policy,'_path',lambda:tmp_path/'fixture-license-policy.json')
    policy.configure(model,{'mode':'cost_recovery','acknowledge_responsibility':True,
        'evidence_url':'https://example.org/generated-test-artifacts','reason':'Generated fixture data; no third-party checkpoint is executed',
        'free_access_confirmed':False,'authorization_basis':'written_permission','confirm_risk_twice':True},1)
