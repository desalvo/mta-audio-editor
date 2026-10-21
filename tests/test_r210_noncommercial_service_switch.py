"""Global admission switch is not an authorization for ambiguous weights."""
import pytest
from app import model_license_policy as policy


def test_commercial_switch_gates_billable_and_keeps_unknown_weights_blocked(tmp_path, monkeypatch):
    from app import studio_catalog
    monkeypatch.setattr(studio_catalog, 'root', lambda: tmp_path)
    assert policy.commercial_service_enabled() is True
    policy.configure_commercial_service({'enabled':False,'acknowledge_impact':True,
        'confirm_risk_twice':True,'reason':'Isolated non-commercial server'},17)
    assert policy.commercial_service_enabled() is False
    with pytest.raises(policy.LicenseDenied,match='globally disabled'):
        policy.evaluate_model('whisper')
    with pytest.raises(policy.LicenseDenied,match='pending license review'):
        policy.evaluate_model('chordformer')
    with pytest.raises(policy.LicenseDenied,match='pending license review'):
        policy.evaluate_model('audio-separator-weights')
    with pytest.raises(policy.LicenseDenied,match='pending license review'):
        policy.evaluate_model('drumsep-weights')


def test_switch_requires_double_confirmation(tmp_path, monkeypatch):
    from app import studio_catalog
    monkeypatch.setattr(studio_catalog, 'root', lambda: tmp_path)
    params={'enabled':False,'acknowledge_impact':True,'confirm_risk_twice':False,
            'reason':'Documented noncommercial deployment'}
    with pytest.raises(ValueError,match='double confirmation'):
        policy.configure_commercial_service(params,23)
    assert policy.commercial_service_enabled() is True
