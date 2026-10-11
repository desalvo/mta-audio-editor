"""r189: self-contained integration configuration and endpoint hardening."""
from pathlib import Path
import os
import pytest
from app.ace_step_http_worker import endpoint_base

ROOT = Path(__file__).resolve().parents[1]

def test_sidecar_allowlist(monkeypatch):
    monkeypatch.setenv('MTA_ACE_STEP_URL', 'http://ace-step:8001')
    monkeypatch.delenv('MTA_ACE_STEP_TRUSTED_HOST', raising=False)
    with pytest.raises(ValueError):
        endpoint_base()
    monkeypatch.setenv('MTA_ACE_STEP_TRUSTED_HOST', 'ace-step')
    assert endpoint_base() == 'http://ace-step:8001'
    for bad in ('evil.test', 'ace-step.evil.test', '127.0.0.2'):
        monkeypatch.setenv('MTA_ACE_STEP_URL', f'http://{bad}:8001')
        with pytest.raises(ValueError):
            endpoint_base()

def test_manifests_do_not_embed_weights_or_publish_api():
    compose = (ROOT/'docker-compose.yml').read_text()
    k8s = (ROOT/'k8s/base/deployment.yaml').read_text()
    assert 'ace-checkpoints:/app/checkpoints' in compose
    assert 'MTA_ACE_STEP_TRUSTED_HOST: ace-step' in compose
    assert '8001:8001' not in compose
    assert 'name: ace-step' in k8s
    assert 'claimName: mta-ace-checkpoints' in k8s
    assert 'value: http://127.0.0.1:8001' in k8s
    assert 'ace-pvc.yaml' in (ROOT/'k8s/base/kustomization.yaml').read_text()

def test_desktop_launch_requires_user_consent(tmp_path):
    from app.ace_step_local import launch
    executable = tmp_path / 'ace-api'
    executable.write_text('#!/bin/sh\nexit 0\n')
    executable.chmod(0o755)
    with pytest.raises(RuntimeError, match='--allow-model-download'):
        launch(str(executable), model_dir=str(tmp_path / 'models'))
    assert launch(str(executable), model_dir=str(tmp_path / 'models'), confirm_download=True) == 0
