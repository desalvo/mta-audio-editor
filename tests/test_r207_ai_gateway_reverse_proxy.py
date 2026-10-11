from pathlib import Path
import pytest
from app.ace_step_http_worker import endpoint_base
from app import ai_gateway

ROOT = Path(__file__).resolve().parents[1]

def test_public_gateway_endpoint_allowlisted(monkeypatch):
    monkeypatch.setenv('MTA_ACE_STEP_URL', 'https://mta.example.org:443/api/ai-gateway')
    monkeypatch.setenv('MTA_ACE_STEP_TRUSTED_HOST', 'mta.example.org')
    monkeypatch.setenv('MTA_ACE_STEP_TOKEN', 'user-token')
    assert endpoint_base() == 'https://mta.example.org:443/api/ai-gateway'
    monkeypatch.setenv('MTA_ACE_STEP_URL', 'https://mta.example.org:443/admin/ai-tokens')
    with pytest.raises(ValueError): endpoint_base()

def test_proxy_files_keep_ace_private():
    root = ROOT / 'deploy/remote-ai'
    nginx = (root/'kubernetes/ingress-nginx.yaml').read_text()
    haproxy = (root/'kubernetes/ingress-haproxy.yaml').read_text()
    backend = (root/'kubernetes/backend.yaml').read_text()
    docker = (root/'docker-haproxy/haproxy.cfg').read_text()
    for item in (nginx,haproxy,backend,docker):
        assert 'port: 8001' not in item and ':8001 check' not in item
    assert 'mta-vm' in nginx and 'mta-vm' in haproxy
    assert '8080' in backend and '8080' in docker

def test_gateway_only_allowed_paths():
    assert 'release_task' in ai_gateway.ALLOWED
    assert 'api/admin/ai-tokens' not in ai_gateway.ALLOWED
