"""Restricted checkpoints require documented authorization and double confirmation."""
import pytest
from app import model_license_policy as policy


def test_two_confirmations_and_permission_basis(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    base={'mode':'free_only','acknowledge_responsibility':True,
          'evidence_url':'https://example.org/written-authorization',
          'reason':'Written permission reviewed for this exact checkpoint and hosting use',
          'free_access_confirmed':True}
    with pytest.raises(ValueError,match='second explicit confirmation'):
        policy.configure('drumsep-weights',base,19)
    with pytest.raises(ValueError,match='authorization basis'):
        policy.configure('drumsep-weights',{**base,'confirm_risk_twice':True},19)
    with pytest.raises(ValueError,match='Unknown checkpoint permissions'):
        policy.configure('drumsep-weights',{**base,'confirm_risk_twice':True,'authorization_basis':'noncommercial_context'},19)
    policy.configure('drumsep-weights',{**base,'confirm_risk_twice':True,'authorization_basis':'written_permission'},19)
    decision=policy.evaluate_model('drumsep-weights')
    assert not decision.billable
    assert policy.catalog()[0]['manual_activation_does_not_grant_rights']


def test_unknown_weights_stay_blocked(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    for model in ('chordformer','audio-separator-weights','drumsep-weights','madmom'):
        with pytest.raises(policy.LicenseDenied):policy.evaluate_model(model)
