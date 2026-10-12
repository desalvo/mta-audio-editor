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
