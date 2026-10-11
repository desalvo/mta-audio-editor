import pytest
from app import ace_step_desktop_manager as d


def test_remote_config_and_secret_never_returned(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR', str(tmp_path))
    result = d.configure_connection(mode='remote', url='https://ace.example.org:8001', token='secret-token')
    assert result['mode'] == 'remote' and result['has_token'] is True
    assert 'secret-token' not in str(result)
    assert (tmp_path/'connection.json').stat().st_mode & 0o077 == 0
    assert d.connection()['url'] == 'https://ace.example.org:8001'
    assert d.configure_connection(mode='remote', url='https://ace.example.org:8001')['has_token']
    assert d.auto_start_server()['server_running'] is False

def test_remote_requires_https_token_and_trusted_host(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR', str(tmp_path))
    for url, token in [('http://ace.example.org:8001','x'), ('https://ace.example.org:8001',''), ('https://127.0.0.1:8001','x')]:
        with pytest.raises(ValueError): d.configure_connection(mode='remote',url=url,token=token)

def test_local_switch_preserves_cache(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR', str(tmp_path))
    (tmp_path/'models').mkdir()
    (tmp_path/'models'/'keep').write_text('x')
    d.configure_connection(mode='remote',url='https://ace.example.org:8001',token='secret')
    result=d.configure_connection(mode='local')
    assert result['mode']=='local'
    assert (tmp_path/'models'/'keep').read_text()=='x'
