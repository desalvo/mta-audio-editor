"""Admin model catalog effective license admission and UI contract regression."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import model_license_policy as policy, studio_admin


def test_admin_catalog_reflects_backend_denial_and_ui_contract(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    from app import service_regime
    monkeypatch.setattr(service_regime, 'current_regime', lambda: service_regime.Regime.COMMERCIAL)
    monkeypatch.setattr(policy, 'commercial_service_enabled', lambda: True)
    from app.storage import _atomic_json_write
    _atomic_json_write(policy._path(), {'madmom': {'mode':'free_only', 'authorization_basis':'noncommercial_context'}})
    app=FastAPI()
    studio_admin.register_routes(app, lambda request: {'id': 1, 'role':'admin'})
    response=TestClient(app).get('/api/admin/ai/studio/models')
    assert response.status_code == 200
    entry=next(x for x in response.json()['licenses'] if x['id']=='madmom')
    assert entry['mode']=='free_only'
    assert entry['effective_mode']=='disabled'
    assert entry['available_in_current_regime'] is False
    assert entry['license_denial_reason']
    try:
        policy.evaluate_model('madmom')
    except policy.LicenseDenied:
        pass
    else:
        raise AssertionError('Backend admitted model blocked by catalog')
    js=Path(__file__).resolve().parents[1]/'app/static/ai_studio.js'
    source=js.read_text()
    assert 'm.available_in_current_regime' in source
    assert 'm.effective_mode' in source
    assert 'm.license_denial_reason' in source
    assert 'data-license-availability' in source
