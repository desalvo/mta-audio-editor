from pathlib import Path
import importlib.util
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'scripts/server_packages'


def load_validator():
    spec = importlib.util.spec_from_file_location('server_validator', PKG / 'validate_stage.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_stage_rejects_missing_wheels(tmp_path):
    app = tmp_path / 'application' / 'app'
    app.mkdir(parents=True)
    (app / 'main.py').write_text('')
    (app / 'ai_cgroup_launcher.py').write_text('')
    (tmp_path / 'application' / 'requirements.txt').write_text('fastapi==1\n')
    assert any('wheelhouse' in s for s in load_validator().validate(tmp_path))


def test_stage_accepts_offline_bundle(tmp_path):
    app = tmp_path / 'application' / 'app'
    app.mkdir(parents=True)
    (app / 'main.py').write_text('')
    (app / 'ai_cgroup_launcher.py').write_text('')
    (tmp_path / 'application' / 'requirements.txt').write_text('')
    (tmp_path / 'wheelhouse').mkdir()
    with zipfile.ZipFile(tmp_path / 'wheelhouse' / 'demo-0.1-py3-none-any.whl', 'w') as z:
        z.writestr('demo-0.1.dist-info/WHEEL', 'Wheel-Version: 1.0\n')
    lock_spec = importlib.util.spec_from_file_location('lock', PKG / 'wheelhouse_lock.py')
    lock = importlib.util.module_from_spec(lock_spec)
    lock_spec.loader.exec_module(lock)
    (tmp_path / 'wheelhouse.lock.json').write_text(__import__('json').dumps({'schema': lock.SCHEMA, 'wheels': lock.inventory(tmp_path)}))
    assert load_validator().validate(tmp_path) == []


def test_scripts_syntax_and_offline_guard():
    for name in ('build_deb.sh', 'build_rpm.sh', 'postinst', 'prerm'):
        subprocess.run(['bash', '-n', str(PKG / name)], check=True)
    assert 'install_runtime.py' in (PKG / 'postinst').read_text()
    assert '--no-index' in (PKG / 'install_runtime.py').read_text()
    assert 'install_runtime.py' in (PKG / 'build_rpm.sh').read_text()


def test_desktop_and_agent_not_confused():
    text = (PKG / 'build_deb.sh').read_text()
    assert 'Package: mta-audio-editor-server' in text
    assert 'mta-proxmox-gpu-agent' not in text

def test_wheel_lock_rejects_tampering(tmp_path):
    import json
    (tmp_path / 'wheelhouse').mkdir()
    path = tmp_path / 'wheelhouse' / 'demo-0.1-py3-none-any.whl'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('demo-0.1.dist-info/WHEEL', 'Wheel-Version: 1.0\n')
    spec = importlib.util.spec_from_file_location('lock', PKG / 'wheelhouse_lock.py')
    lock = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lock)
    (tmp_path / 'wheelhouse.lock.json').write_text(json.dumps({'schema': lock.SCHEMA, 'wheels': lock.inventory(tmp_path)}))
    with zipfile.ZipFile(path, 'a') as z:
        z.writestr('extra', 'tampered')
    import pytest
    with pytest.raises(ValueError, match='differs'):
        lock.verify(tmp_path)


def test_release_build_requires_offline_proof(tmp_path):
    app = tmp_path / 'stage/application/app'
    app.mkdir(parents=True)
    (app / 'main.py').write_text('')
    (app / 'ai_cgroup_launcher.py').write_text('')
    (app.parent / 'requirements.txt').write_text('')
    (tmp_path / 'stage/wheelhouse').mkdir()
    with zipfile.ZipFile(tmp_path / 'stage/wheelhouse/demo-0.1-py3-none-any.whl', 'w') as z:
        z.writestr('demo-0.1.dist-info/WHEEL', 'Wheel-Version: 1.0\n')
    subprocess.run(['python3', str(PKG / 'wheelhouse_lock.py'), 'create', str(tmp_path / 'stage')], check=True)
    result = subprocess.run(['bash', str(PKG / 'build_deb.sh')], capture_output=True, text=True,
        env={**__import__('os').environ, 'MTA_SERVER_STAGE': str(tmp_path / 'stage'),
             'MTA_SERVER_VERSION': '0.3.0~early.208', 'MTA_SERVER_OUTPUT': str(tmp_path / 'out'),
             'MTA_SERVER_RELEASE_READY': '1'})
    assert result.returncode != 0
    assert 'Missing offline runtime proof' in result.stderr


def test_runtime_proof_rejects_different_requirements(tmp_path):
    import sys
    stage = tmp_path
    (stage / 'application').mkdir()
    (stage / 'application/requirements.txt').write_text('')
    (stage / 'wheelhouse.lock.json').write_text('{}')
    sys.path.insert(0, str(PKG))
    try:
        from verify_offline_runtime import metadata, check_proof
        (stage / 'offline-runtime-proof.json').write_text(__import__('json').dumps(metadata(stage)))
        check_proof(stage)
        (stage / 'application/requirements.txt').write_text('fastapi==1\n')
        import pytest
        with pytest.raises(ValueError, match='stale'):
            check_proof(stage)
    finally:
        sys.path.pop(0)
