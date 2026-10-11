from pathlib import Path
import pytest
from app import ace_step_desktop_manager as manager


def test_installer_requires_consent(monkeypatch,tmp_path):
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR',str(tmp_path))
    with pytest.raises(ValueError,match='consent'):
        manager.install(confirmed=False)
    assert not (tmp_path/'source').exists()


def test_server_requires_consent_and_install(monkeypatch,tmp_path):
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR',str(tmp_path))
    with pytest.raises(ValueError):manager.start_server(confirmed_model_download=False)
    with pytest.raises(RuntimeError):manager.start_server(confirmed_model_download=True)


def test_status_has_no_network_or_install_side_effect(monkeypatch,tmp_path):
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR',str(tmp_path))
    result=manager.status()
    assert result['installed'] is False
    assert not (tmp_path/"source").exists()


def test_autostart_requires_persisted_consent(monkeypatch, tmp_path):
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR', str(tmp_path))
    def unexpected(**kwargs):
        raise AssertionError('server must not be started without consent')
    monkeypatch.setattr(manager, 'start_server', unexpected)
    assert manager.auto_start_server()['auto_start_enabled'] is False


def test_autostart_reuses_previous_permission(monkeypatch, tmp_path):
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR', str(tmp_path))
    manager._remember_consent()
    calls = []
    monkeypatch.setattr(manager, 'start_server', lambda **kwargs: calls.append(kwargs) or {'server_running':True})
    assert manager.auto_start_server()['server_running'] is True
    assert calls == [{'confirmed_model_download':True, 'remember_consent':False}]
    manager.stop_server(disable_auto_start=True)
    assert not manager._consent_file().exists()


def test_native_shutdown_stops_only_owned_worker(monkeypatch, tmp_path):
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR', str(tmp_path))
    # A lifecycle shutdown without an MTA-owned process must be a no-op.
    monkeypatch.setattr(manager, '_PROCESS', None)
    assert manager.stop_server()['server_running'] is False


def test_install_progress_fields_and_no_fabricated_model_percent(monkeypatch, tmp_path):
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR', str(tmp_path))
    manager._update_progress('clone', 42, 'Receiving objects: 42%')
    assert manager.status()['task']['progress_percent'] == 42
    manager._update_progress('dependencies', None, 'Installing packages')
    assert manager.status()['task']['progress_percent'] is None
    model_cache = tmp_path / 'models'
    model_cache.mkdir()
    (model_cache / 'checkpoint.part').write_bytes(b'a' * 73)
    assert manager._cache_size(model_cache) == 73
