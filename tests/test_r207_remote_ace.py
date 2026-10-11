import pytest
from app.ace_step_http_worker import endpoint_base

def test_remote_https_allowlisted(monkeypatch):
    monkeypatch.setenv('MTA_ACE_STEP_URL', 'https://ace.example.internal:8443')
    monkeypatch.setenv('MTA_ACE_STEP_TRUSTED_HOST', 'ace.example.internal')
    monkeypatch.setenv('MTA_ACE_STEP_TOKEN', 'a-secret')
    assert endpoint_base() == 'https://ace.example.internal:8443'

def test_remote_requires_tls_and_token(monkeypatch):
    monkeypatch.setenv('MTA_ACE_STEP_TRUSTED_HOST', 'ace.example.internal')
    monkeypatch.delenv('MTA_ACE_STEP_TOKEN', raising=False)
    monkeypatch.setenv('MTA_ACE_STEP_URL', 'https://ace.example.internal:8443')
    with pytest.raises(ValueError, match='token'):
        endpoint_base()
    monkeypatch.setenv('MTA_ACE_STEP_TOKEN', 'a-secret')
    monkeypatch.setenv('MTA_ACE_STEP_URL', 'http://ace.example.internal:8443')
    with pytest.raises(ValueError, match='HTTPS'):
        endpoint_base()

def test_remote_denies_untrusted_and_redirect_lookalike(monkeypatch):
    monkeypatch.setenv('MTA_ACE_STEP_TRUSTED_HOST', 'ace.example.internal')
    monkeypatch.setenv('MTA_ACE_STEP_TOKEN', 'a-secret')
    for url in ['https://evil.example:8443', 'https://ace.example.internal.evil:8443', 'https://ace.example.internal:8443/path', 'https://user@ace.example.internal:8443']:
        monkeypatch.setenv('MTA_ACE_STEP_URL', url)
        with pytest.raises(ValueError): endpoint_base()
