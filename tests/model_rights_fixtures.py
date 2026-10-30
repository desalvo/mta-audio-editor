"""Authorize generated test data only; production defaults stay fail-closed."""
def synthetic_review(mode='cost_recovery'):
    return {'mode':mode,'acknowledge_responsibility':True,'free_access_confirmed':True,
            'evidence_url':'https://example.test/synthetic-permission',
            'reason':'Generated test fixtures only;no real checkpoint authorization',
            'authorization_basis':'written_permission','confirm_risk_twice':True,
            'actor_id':0,'reviewed_at':1}


def authorize_fixture(monkeypatch,tmp_path,model):
    from app import model_license_policy as policy
    monkeypatch.setattr(policy,'_path',lambda:tmp_path/'fixture-license-policy.json')
    policy.configure(model,{'mode':'cost_recovery','acknowledge_responsibility':True,
        'evidence_url':'https://example.org/generated-test-artifacts','reason':'Generated fixture data; no third-party checkpoint is executed',
        'free_access_confirmed':False,'authorization_basis':'written_permission','confirm_risk_twice':True},1)


def authorize_singing_fixture(monkeypatch,tmp_path):
    """Both components below are generated test bytes, never installed weights."""
    for model in ('diffsinger-nishiren','diffsinger-vocoder'):
        authorize_fixture(monkeypatch,tmp_path,model)
    monkeypatch.setenv('MTA_NEURAL_SINGER_POLICY_MODEL','diffsinger-nishiren')
    monkeypatch.setenv('MTA_DIFFSINGER_VOCODER_POLICY_MODEL','diffsinger-vocoder')


def offline_singing_fixture(tmp_path):
    """Own synthetic child script and component permission files, not a bank."""
    import json,os
    runtime=tmp_path/'runtime';(runtime/'scripts').mkdir(parents=True,exist_ok=True)
    folder=tmp_path/'.studio-models';folder.mkdir(exist_ok=True)
    (folder/'license-policy.json').write_text(json.dumps({
        name:synthetic_review() for name in ('diffsinger-nishiren','diffsinger-vocoder')}))
    return runtime,{**os.environ,'MTA_DATA_DIR':str(tmp_path),'MTA_STUDIO_OFFLINE_KIND':'diffsinger',
        'MTA_NEURAL_SINGER_POLICY_MODEL':'diffsinger-nishiren',
        'MTA_DIFFSINGER_VOCODER_POLICY_MODEL':'diffsinger-vocoder',
        'MTA_DIFFSINGER_FORMAT':'native','MTA_DIFFSINGER_ROOT':str(runtime)}
