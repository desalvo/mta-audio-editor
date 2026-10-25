"""Catalog/admission parity tests without any live provider or server."""
import json
import pytest
from app import model_license_policy as policy
from app import service_regime


def test_catalog_reports_disabled_and_available_models(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, '_path', lambda: tmp_path/'license-policy.json')
    monkeypatch.setattr(service_regime, 'current_regime', lambda: service_regime.Regime.COMMERCIAL)
    items={entry['id']:entry for entry in policy.catalog()}
    assert items['madmom']['available_in_current_regime'] is False
    assert items['madmom']['effective_mode']=='disabled'
    assert items['basic-pitch']['available_in_current_regime'] is True


def test_restored_noncommercial_rights_cannot_bypass_commercial_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, '_path', lambda: tmp_path/'license-policy.json')
    monkeypatch.setattr(service_regime, 'current_regime', lambda: service_regime.Regime.COMMERCIAL)
    (tmp_path/'license-policy.json').write_text(json.dumps({
      'madmom':{'mode':'free_only','authorization_basis':'noncommercial_context'},
      'diffsinger-qixuan':{'mode':'cost_recovery','authorization_basis':'written_permission'}}))
    with pytest.raises(policy.LicenseDenied):policy.evaluate_model('madmom')
    with pytest.raises(policy.LicenseDenied):policy.evaluate_model('diffsinger-qixuan')
    items={entry['id']:entry for entry in policy.catalog()}
    assert not items['madmom']['available_in_current_regime']
    assert not items['diffsinger-qixuan']['available_in_current_regime']
    assert items['diffsinger-qixuan']['mode']=='cost_recovery'
    assert items['diffsinger-qixuan']['effective_mode']=='disabled'
