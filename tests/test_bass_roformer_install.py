import contextlib
import hashlib
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import ai_worker_registry, auth, bass_roformer_install as install, bass_roformer_runtime, model_asset_admin
from app.model_asset_admin_routes import register_routes


@pytest.fixture
def fake_install(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    for name in ('MTA_BASS_ROFORMER_ROOT', 'MTA_BASS_ROFORMER_CONFIG', 'MTA_BASS_ROFORMER_PYTHON', 'MTA_BASS_ROFORMER_CHECKPOINT'):
        monkeypatch.delenv(name, raising=False)
    config, weights = b'test yaml', b'test weights'
    monkeypatch.setattr(install, 'CONFIG', ('model.yaml', len(config), hashlib.sha256(config).hexdigest()))
    monkeypatch.setattr(install, 'WEIGHTS', ('model.ckpt', len(weights), hashlib.sha256(weights).hexdigest()))
    monkeypatch.setattr(bass_roformer_runtime, 'CHECKPOINT_SHA256', hashlib.sha256(weights).hexdigest())
    monkeypatch.setattr(model_asset_admin, 'mutation', lambda job_id=None: contextlib.nullcontext())
    monkeypatch.setattr(ai_worker_registry, 'worker_python', lambda kind: sys.executable)
    phases = []
    def download(spec, destination, cancelled, progress):
        assert not cancelled()
        destination.write_bytes(config if spec == install.CONFIG else weights)
        progress('download', spec[1], spec[1])
    def run(command, cwd, cancelled, progress, phase):
        phases.append(phase)
        if phase == 'source-init':
            (cwd / 'source').mkdir()
            (cwd / 'source' / 'inference.py').write_text('# test')
        if phase == 'creating-runtime':
            (cwd / 'venv/bin').mkdir(parents=True)
            (cwd / 'venv/bin/python').write_text('# test')
        progress(phase, None, None)
    monkeypatch.setattr(install, '_download', download)
    monkeypatch.setattr(install, '_run', run)
    monkeypatch.setattr(install.subprocess, 'check_output', lambda args, **kw:
                        install.COMMIT if 'rev-parse' in args else 'torch==1\ntorchaudio==1\ntorchvision==1\n')
    return phases, weights


def test_installer_activates_only_after_strict_validation(fake_install):
    phases, weights = fake_install
    result = install.install('cpu', lambda: False, lambda *args: None, job_id='test')
    assert result['checkpoint_verified'] and result['model_load_verified'] and not result['inference_tested']
    assert phases[-1] == 'strict-model-load'
    assert bass_roformer_runtime.managed_checkpoint().read_bytes() == weights
    assert install.receipt()['checkpoint_validated']
    assert bass_roformer_runtime.configured()


def test_failed_model_validation_preserves_previous_runtime(fake_install, monkeypatch):
    install.install('cpu', lambda: False, lambda *args: None)
    old = (install.root() / 'runtime.json').read_bytes()
    original = install._run
    def fail(command, cwd, cancelled, progress, phase):
        if phase == 'strict-model-load': raise RuntimeError('invalid model')
        return original(command, cwd, cancelled, progress, phase)
    monkeypatch.setattr(install, '_run', fail)
    with pytest.raises(RuntimeError, match='invalid model'):
        install.install('cpu', lambda: False, lambda *args: None)
    assert (install.root() / 'runtime.json').read_bytes() == old
    assert len(list((install.root() / 'runtimes').iterdir())) == 1


def test_config_tampering_prevents_managed_runtime_activation(fake_install):
    install.install('cpu', lambda: False, lambda *args: None)
    install.receipt()['config'].write_bytes(b'bad')
    assert install.receipt() is None
    assert not bass_roformer_runtime.configured()


def test_install_endpoint_requires_admin_and_strict_body(monkeypatch):
    def client(role):
        app = FastAPI(); register_routes(app, lambda req: {'id': 7, 'role': role})
        return TestClient(app)
    url = '/api/admin/ai/bass-roformer/runtime/install'
    assert client('user').post(url, json={'accept_licenses': True, 'device': 'cpu'}).status_code == 403
    assert client('admin').post(url, json={'accept_licenses': False, 'device': 'cpu'}).status_code == 422
    assert client('admin').post(url, json={'accept_licenses': True, 'device': 'cpu', 'url':'https://bad'}).status_code == 422
    assert client('admin').post(url, json={'accept_licenses': True, 'device': 'fake'}).status_code == 422


def test_install_endpoint_queues_fixed_recipe_and_progress(tmp_path, monkeypatch):
    from app import ai_arranger_runtime as queue
    captured = {}
    def start(pid, operation, fn, **kwargs):
        captured.update(pid=pid, operation=operation, fn=fn, **kwargs)
        return kwargs['job_id'], {'state': 'queued'}
    monkeypatch.setattr(queue, 'start', start)
    def fake_install(device, cancelled, progress, job_id=None):
        assert device == 'rocm' and not cancelled() and job_id == captured['job_id']
        progress('configuration', 4, 4)
        return {'installed': True, 'inference_tested': False}
    monkeypatch.setattr(install, 'install', fake_install)
    app = FastAPI(); register_routes(app, lambda req: {'id': 7, 'role': 'admin'})
    response = TestClient(app).post('/api/admin/ai/bass-roformer/runtime/install',
                                    json={'accept_licenses': True, 'device': 'rocm'})
    assert response.status_code == 200 and captured['operation'] == 'worker:studio-install'
    assert captured['payload']['actor_user_id'] == 7 and captured['cancellable']
    class Event:
        def is_set(self): return False
    path = tmp_path / 'progress.json'
    captured['fn'](path, Event())
    import json
    assert json.loads(path.read_text())['result']['inference_tested'] is False


def test_download_rejects_wrong_bytes_without_publishing(tmp_path, monkeypatch):
    import io
    from app import secure_https
    monkeypatch.setattr(secure_https, 'https_urlopen', lambda *args, **kwargs: io.BytesIO(b'bad'))
    with pytest.raises(ValueError, match='SHA-256'):
        install._download(('test', 3, '0' * 64), tmp_path / 'partial', lambda: False, lambda *args: None)


def test_torchaudio_stable_abi_uses_published_versions():
    assert 'torchaudio==2.11.0+cpu' in install.torch_arguments('cpu')
    assert 'torchaudio==2.11.0+cu128' in install.torch_arguments('cuda')
    assert 'torchaudio==2.11.0+rocm7.2' in install.torch_arguments('rocm')


@pytest.mark.parametrize('path,body',[
    ('runtime/install',{'accept_licenses':True,'device':'auto'}),
    ('runtime/remove',{}),('weights/install',{'accept_licenses':True}),('weights/remove',{}),
])
def test_all_bass_lifecycle_routes_require_administrator(path,body):
    app=FastAPI();register_routes(app,lambda req:{'id':9,'role':'user'})
    response=TestClient(app).post('/api/admin/ai/bass-roformer/'+path,json=body)
    assert response.status_code==403


@pytest.mark.parametrize('body',[{}, {'accept_licenses':False,'device':'cpu'},
    {'accept_licenses':True,'device':'arbitrary'},{'accept_licenses':True,'device':'cpu','url':'https://example.test'}])
def test_runtime_install_rejects_unreviewed_or_open_parameters(body):
    app=FastAPI();register_routes(app,lambda req:{'id':9,'role':'admin'})
    assert TestClient(app).post('/api/admin/ai/bass-roformer/runtime/install',json=body).status_code==422


def test_runtime_and_checkpoint_removal_are_independent(fake_install):
    install.install('cpu',lambda:False,lambda *args:None)
    install.remove(checkpoint=True)
    assert install.receipt() and not bass_roformer_runtime.managed_checkpoint().exists()
    assert not bass_roformer_runtime.configured()
    install.remove(checkpoint=False)
    assert not install.receipt()
