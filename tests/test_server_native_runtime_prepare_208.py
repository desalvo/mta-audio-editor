from pathlib import Path
import importlib.util
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/server_packages/prepare_runtime.py'
spec = importlib.util.spec_from_file_location('mta_runtime_prepare', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_refuses_incomplete_source(tmp_path):
    (tmp_path / 'requirements.txt').write_text('demo==1\n')
    with pytest.raises(ValueError, match='entrypoints'):
        module.prepare(tmp_path, tmp_path / 'stage', tmp_path / 'requirements.txt')


def test_refuses_dirty_stage(tmp_path):
    app = tmp_path / 'app'
    app.mkdir()
    (app / 'main.py').touch()
    (app / 'ai_cgroup_launcher.py').touch()
    (tmp_path / 'requirements.txt').write_text('demo==1\n')
    stage = tmp_path / 'stage'
    stage.mkdir()
    (stage / 'old').touch()
    with pytest.raises(ValueError, match='non-empty'):
        module.prepare(tmp_path, stage, tmp_path / 'requirements.txt')
