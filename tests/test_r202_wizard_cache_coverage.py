"""Exercise installer contract and ACE-Step runtime introspection failure paths."""
from pathlib import Path
import json
import subprocess

import pytest
from app import ace_model_cache, ace_step_readiness

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/install_ace_step.sh'


def test_single_file_contract():
    script = SCRIPT.read_text()
    assert script.startswith('#!/usr/bin/env bash')
    assert 'ACE_STEP_INSTALLATION.md' in (ROOT / 'README.md').read_text()
    assert 'ACE_STEP_INSTALLATION.md' in (ROOT / 'README_IT.md').read_text()
    assert not (ROOT / 'ACE_STEP_LXC_WIZARD.md').exists()
    assert SCRIPT.stat().st_mode & 0o111
    assert '--uninstall' in script
    assert 'rm -rf -- "$BASE/ace-step" "$BASE/venv-ace-step"' in script
    assert 'Type DELETE' in script
    assert '--purge-data requires --uninstall' in script
    help_result = subprocess.run([str(SCRIPT), '--help'], capture_output=True, text=True)
    assert help_result.returncode == 0
    assert '--uninstall' in help_result.stdout


def test_cache_absent_and_file_limit(tmp_path):
    missing = tmp_path / 'missing'
    result = ace_model_cache.cache_status(roots=(missing,))
    assert result['cache_available'] is False
    assert result['bytes_cached'] == 0
    assert result['file_count'] == 0
    assert result['models_ready'] is None
    assert result['inference_verified'] is False
    for n in (0, -1, 100001):
        with pytest.raises(ValueError):
            ace_model_cache.cache_status(roots=(), file_limit=n)


def test_cache_files_truncation_and_symlink(tmp_path):
    root = tmp_path / 'cache'; root.mkdir()
    (root / 'first').write_bytes(b'abc')
    (root / 'second').write_bytes(b'abcd')
    (root / 'nested').mkdir()
    (root / 'nested' / 'third').write_bytes(b'12345')
    (root / 'skip').symlink_to(root / 'first')
    (root / 'linked_dir').symlink_to(root / 'nested', target_is_directory=True)
    result = ace_model_cache.cache_status(roots=(root,))
    assert result['cache_available'] is True
    assert result['file_count'] == 3
    assert result['bytes_cached'] == 12
    assert result['scan_truncated'] is False
    capped = ace_model_cache.cache_status(roots=(root,), file_limit=1)
    assert capped['scan_truncated'] is True
    assert capped['file_count'] == 1


def test_readiness_unconfigured(monkeypatch):
    monkeypatch.setattr(ace_step_readiness, 'configured_worker', lambda: None)
    result = ace_step_readiness.readiness(probe=True)
    assert result['worker_configured'] is False
    assert result['reason'] == 'worker_not_configured'
    assert result['ready_for_real_generation'] is False


@pytest.mark.parametrize('mode,expected', [('fail','capability_probe_failed'), ('json','probe_failed'), ('invalid','invalid_capabilities'),('good','real_inference_not_verified'), ('error','probe_failed')])
def test_readiness_probes(monkeypatch, mode, expected):
    monkeypatch.setattr(ace_step_readiness, 'configured_worker', lambda: '/usr/bin/worker')
    class Output:
        returncode = 1 if mode == 'fail' else 0
        stdout = ('{' if mode == 'json' else json.dumps({'protocol': 'bad'} if mode == 'invalid' else {'protocol': 'mta.ai.worker.v1', 'supports_audio_input': True}))
    def runner(*args, **kwargs):
        if mode == 'error':
            raise OSError('broken')
        return Output()
    monkeypatch.setattr(ace_step_readiness.subprocess,'run',runner)
    result = ace_step_readiness.readiness(probe=True)
    assert result['reason'] == expected
    assert result['inference_verified'] is False
    if mode == 'good':
        assert result['worker_capabilities_verified'] is True
        assert result['accepts_source_audio'] is True


def test_readiness_server_and_timeout(monkeypatch):
    monkeypatch.setattr(ace_step_readiness, 'configured_worker', lambda: '/usr/bin/worker')
    monkeypatch.setenv('MTA_AI_READINESS_PROBE_SERVER', 'true')
    def runner(args, **kwargs):
        class Output:
            returncode = 0
            stdout = json.dumps({'server_reachable': True} if '--check-server' in args else {'protocol':'mta.ai.worker.v1','supports_audio_input':False})
        return Output()
    monkeypatch.setattr(ace_step_readiness.subprocess,'run',runner)
    result=ace_step_readiness.readiness(probe=True)
    assert result['server_reachable'] is True
    assert result['accepts_source_audio'] is False
    for seconds in (0, 31):
        with pytest.raises(ValueError):
            ace_step_readiness.readiness(probe=True, timeout_seconds=seconds)


def test_local_launcher_guards(tmp_path, monkeypatch):
    from app import ace_step_local
    with pytest.raises(ValueError):
        ace_step_local.launch('relative-file', model_dir=str(tmp_path))
    exe = tmp_path / 'run'; exe.write_text('#!/bin/sh\n'); exe.chmod(0o755)
    alias = tmp_path / 'alias'; alias.symlink_to(exe)
    with pytest.raises(ValueError):
        ace_step_local.launch(str(alias), model_dir=str(tmp_path))
    cache = tmp_path / 'cache'
    with pytest.raises(RuntimeError):
        ace_step_local.launch(str(exe), model_dir=str(cache))
    assert cache.is_dir()
    seen = {}
    def fake_call(cmd, env):
        seen['cmd'] = cmd; seen['env'] = env
        return 0
    monkeypatch.setattr(ace_step_local.subprocess, 'call', fake_call)
    assert ace_step_local.launch(str(exe), model_dir=str(cache), confirm_download=True) == 0
    assert seen['cmd'] == [str(exe)]
    assert seen['env']['HF_HOME'] == str(cache / 'huggingface')
    assert seen['env']['ACESTEP_MODE'] == 'api'
    (cache / 'present').touch()
    assert ace_step_local.launch(str(exe), model_dir=str(cache)) == 0


def test_desktop_manager_cache_status_consent_and_install_guards(tmp_path, monkeypatch):
    from app import ace_step_desktop_manager as mgr
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR', str(tmp_path / 'ace-home'))
    home = mgr.home()
    assert home == (tmp_path / 'ace-home').resolve()
    assert mgr._previous_consent() is False
    assert mgr._cache_size(home / 'models') == 0
    cache = home / 'models'; cache.mkdir(parents=True)
    (cache / 'first.bin').write_bytes(b'1234567')
    (cache / 'nested').mkdir()
    (cache / 'nested' / 'second.bin').write_bytes(b'abcd')
    assert mgr._cache_size(cache) == 11
    mgr._update_progress('clone', 25, 'x' * 300)
    assert mgr._TASK['progress_percent'] == 25
    assert len(mgr._TASK['message']) == 240
    mgr._remember_consent()
    assert mgr._previous_consent() is True
    data = json.loads(mgr._consent_file().read_text())
    assert data['auto_start'] is True
    assert data['model_download_consent'] is True
    mgr._consent_file().write_text('broken')
    assert mgr._previous_consent() is False
    with pytest.raises(ValueError):
        mgr.install(confirmed=False)
    monkeypatch.setattr(mgr.shutil, 'which', lambda cmd: None)
    with pytest.raises(RuntimeError):
        mgr.install(confirmed=True)
    result = mgr.status()
    assert result['installed'] is False
    assert result['server_running'] is False
    assert result['auto_start_enabled'] is True
    mgr.stop_server(disable_auto_start=True)
    assert not mgr._consent_file().exists()
    monkeypatch.setattr(mgr, 'ensure_local', lambda **kwargs: (_ for _ in ()).throw(RuntimeError('fail')))
    mgr._remember_consent()
    assert mgr.auto_start_server()['task']['startup_error'] == 'fail'
