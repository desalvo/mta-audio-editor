"""Regression tests for offline native runtime transitions."""
import importlib.util
from pathlib import Path
import sys

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/server_packages/install_runtime.py'
spec = importlib.util.spec_from_file_location('mta_runtime_test', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_rejects_missing_payload_without_touching_previous_venv(tmp_path):
    app = tmp_path / 'application'
    app.mkdir()
    (app / 'requirements.txt').write_text('example==1.0\n')
    wheels = tmp_path / 'wheelhouse'
    wheels.mkdir()
    venv = tmp_path / 'server-venv'
    venv.mkdir()
    (venv / 'existing.txt').write_text('preserved')
    try:
        module.install_runtime(sys.executable, app, wheels, venv)
    except RuntimeError as err:
        assert 'wheelhouse' in str(err)
    else:
        raise AssertionError('Incomplete runtime erroneously accepted')
    assert (venv / 'existing.txt').read_text() == 'preserved'


def test_rejects_ambiguous_existing_rollback(tmp_path):
    app = tmp_path / 'application'
    app.mkdir()
    (app / 'requirements.txt').write_text('')
    wheels = tmp_path / 'wheelhouse'
    wheels.mkdir()
    (wheels / 'dummy-1.0-py3-none-any.whl').write_bytes(b'not-used')
    venv = tmp_path / 'venv'
    backup = tmp_path / 'venv.rollback'
    backup.mkdir()
    try:
        module.install_runtime(sys.executable, app, wheels, venv)
    except RuntimeError as err:
        assert 'rollback' in str(err)
    else:
        raise AssertionError('Should stop to avoid overwriting rollback')
    assert backup.is_dir()


def test_failed_promoted_validation_restores_previous_runtime(tmp_path, monkeypatch):
    """A broken post-promotion runtime must never replace the previously working venv."""
    import subprocess

    app = tmp_path / 'application'
    app.mkdir()
    (app / 'requirements.txt').write_text('demo==1\n')
    wheels = tmp_path / 'wheelhouse'
    wheels.mkdir()
    (wheels / 'demo-1-py3-none-any.whl').write_bytes(b'fixture')
    venv = tmp_path / 'server-venv'
    venv.mkdir()
    (venv / 'old-runtime').write_text('keep me')

    def simulated_run(cmd, **kwargs):
        if cmd[1:3] == ['-m', 'venv']:
            stage = Path(cmd[3]); (stage / 'bin').mkdir(parents=True)
            (stage / 'bin' / 'python').write_text('simulated')
            return subprocess.CompletedProcess(cmd, 0)
        if cmd[0] == str(venv / 'bin' / 'python'):
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, 'run', simulated_run)
    import pytest
    with pytest.raises(subprocess.CalledProcessError):
        module.install_runtime(sys.executable, app, wheels, venv)
    assert (venv / 'old-runtime').read_text() == 'keep me'
    assert not (tmp_path / 'server-venv.rollback').exists()
    assert not list(tmp_path.glob('server-venv.staging-*'))


def test_successful_promotion_removes_backup_and_staging(tmp_path, monkeypatch):
    import subprocess
    app = tmp_path / 'application'; app.mkdir()
    (app / 'requirements.txt').write_text('demo==1\n')
    wheels = tmp_path / 'wheelhouse'; wheels.mkdir()
    (wheels / 'demo-1-py3-none-any.whl').write_bytes(b'fixture')
    venv = tmp_path / 'server-venv'; venv.mkdir()
    (venv / 'old-runtime').write_text('old')

    def simulated_run(cmd, **kwargs):
        if cmd[1:3] == ['-m', 'venv']:
            stage = Path(cmd[3]); (stage / 'bin').mkdir(parents=True)
            (stage / 'bin' / 'python').write_text('new')
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(module.subprocess, 'run', simulated_run)
    module.install_runtime(sys.executable, app, wheels, venv)
    assert (venv / 'bin' / 'python').read_text() == 'new'
    assert not (tmp_path / 'server-venv.rollback').exists()
    assert not list(tmp_path.glob('server-venv.staging-*'))
