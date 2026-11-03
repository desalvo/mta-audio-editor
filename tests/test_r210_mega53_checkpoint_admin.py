import hashlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import auth, mega53_runtime, model_asset_admin
from app.model_asset_admin_routes import register_routes


def client(role):
    app = FastAPI()
    register_routes(app, lambda request: {'id': 1, 'role': role})
    return TestClient(app)


def test_explicit_upload_verifies_before_replacing_and_reports_partial_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    for name in ('MTA_MEGA53_ROOT', 'MTA_MEGA53_CONFIG', 'MTA_MEGA53_CHECKPOINT'):
        monkeypatch.delenv(name, raising=False)
    valid = b'test-only-checkpoint'
    monkeypatch.setattr(mega53_runtime, 'MEGA53_V1_SHA256', hashlib.sha256(valid).hexdigest())
    monkeypatch.setattr(model_asset_admin, 'mutation', lambda: __import__('contextlib').nullcontext())
    url = '/api/admin/ai/mega53/checkpoint/install'
    assert client('user').post(url + '?accept_licenses=true', content=valid).status_code == 403
    assert client('admin').post(url, content=valid).status_code == 422
    response = client('admin').post(url + '?accept_licenses=true', content=valid)
    assert response.status_code == 200
    assert response.json() == {'checkpoint_verified': True, 'paths_ready': False,
                               'inference_tested': False, 'scope': 'local-server'}
    destination = mega53_runtime.managed_checkpoint()
    assert destination.read_bytes() == valid
    assert client('admin').post(url + '?accept_licenses=true', content=b'wrong').status_code == 409
    assert destination.read_bytes() == valid
    assert client('admin').post('/api/admin/ai/mega53/checkpoint/verify').json()['checkpoint_verified'] is True
    assert client('user').post('/api/admin/ai/mega53/checkpoint/verify').status_code == 403


def test_upload_does_not_override_operator_configured_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    monkeypatch.setenv('MTA_MEGA53_CHECKPOINT', str(tmp_path / 'external'))
    response = client('admin').post('/api/admin/ai/mega53/checkpoint/install?accept_licenses=true', content=b'x')
    assert response.status_code == 409
    assert not mega53_runtime.managed_checkpoint().exists()
