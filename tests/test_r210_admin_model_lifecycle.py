"""Complete model/runtime actions operate on owned assets and keep separate lifecycles."""
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import ai_runtime_admin as runtime, chord_ml, model_asset_admin as models
from app.model_asset_admin_routes import register_routes


def test_model_remove_queues_the_entire_recipe(tmp_path, monkeypatch):
    from app import ai_arranger_runtime as queue
    from contextlib import nullcontext
    monkeypatch.setenv('MTA_CHORD_ML_MODEL_DIR', str(tmp_path))
    folder = chord_ml.model_dir('btc-hcqt')
    folder.mkdir()
    (folder / 'weights.pt').write_bytes(b'fixture')
    (folder / 'metadata.json').write_text('{}')
    other = chord_ml.model_dir('chordformer')
    other.mkdir()
    monkeypatch.setattr(models, 'mutation', lambda *_: nullcontext())
    monkeypatch.setattr(models, 'recipes', lambda: [
        {'id':'chords-btc-hcqt', 'engine':'chords', 'remove_job_url':'configured'}])
    jobs = []
    def start(_project, _operation, run, *, job_id, payload):
        assert payload['actor_user_id'] == 7
        jobs.append((job_id, run))
        return job_id, {'state':'queued'}
    monkeypatch.setattr(queue, 'start', start)
    actor = {'id':7, 'role':'user'}
    app = FastAPI()
    register_routes(app, lambda _: actor)
    client = TestClient(app)
    url = '/api/admin/ai/model-assets/recipes/chords-btc-hcqt/remove'
    assert client.post(url).status_code == 403
    actor['role'] = 'admin'
    response = client.post(url)
    assert response.status_code == 200 and folder.exists()
    assert response.json()['job_id'] == jobs[0][0]
    class Stop:
        def is_set(self):
            return False
    progress = tmp_path / 'progress.json'
    jobs[0][1](progress, Stop())
    assert not folder.exists() and other.is_dir()
    assert json.loads(progress.read_text())['progress_percent'] == 100


def test_runtime_install_and_remove_do_not_touch_external_files(tmp_path, monkeypatch):
    from app import ai_adapter_identity, ai_arranger_runtime as queue
    from contextlib import nullcontext
    import os
    import sys

    if sys.platform != 'linux':
        pytest.skip('Linux runtime fixture')
    monkeypatch.setattr(runtime, 'MANAGED_RUNTIME_ROOT', tmp_path)
    monkeypatch.setattr(runtime, 'MANAGED_RUNTIME_OWNER', os.geteuid())
    monkeypatch.setattr(ai_adapter_identity, 'MANAGED_RUNTIME_ROOT', tmp_path)
    monkeypatch.setattr(ai_adapter_identity, 'MANAGED_RUNTIME_OWNER', os.geteuid())
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'queue')
    monkeypatch.setattr(models, 'mutation', lambda *_: nullcontext())
    monkeypatch.setattr(runtime, '_installer', lambda: tmp_path / 'installer.py')
    monkeypatch.setenv('MTA_AI_QUEUE_MODE', 'local')
    external = tmp_path / 'external-runtime'
    external.mkdir()
    def build(argv, _):
        generation = argv[argv.index('--runtime-only') + 1]
        folder = tmp_path / ('ai-' + generation) / 'audio'
        binary = folder / 'bin/python'
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b'fixture')
        binary.chmod(0o755)
        (folder / '.mta-ai-ready.json').write_text(json.dumps({'group':'audio','fingerprint':generation}))
        (folder / 'pyvenv.cfg').write_text('include-system-site-packages = false')
    monkeypatch.setattr(runtime, '_run', build)
    runtime.install('cpu', lambda: False, 'job')
    binary, disabled = runtime.override('chords-ml')
    assert Path(binary).is_file() and disabled is False
    assert runtime.override('ace-step') == (None, False)
    runtime.remove('job')
    assert not Path(binary).exists() and external.is_dir()
    assert runtime.override('chords-ml') == (None, True)


@pytest.mark.parametrize('model_id', ['chordmini-btc','chordmini-2e1d'])
def test_chordmini_loader_preserves_strict_mode_and_probe(tmp_path, monkeypatch, model_id):
    import hashlib
    code = tmp_path / 'runtime'
    (code / 'checkpoints').mkdir(parents=True)
    weight = b'weights fixture'
    architecture, name, _, _ = chord_ml.CHORDMINI[model_id]
    sha = hashlib.sha1(f'blob {len(weight)}\0'.encode() + weight, usedforsecurity=False).hexdigest()
    monkeypatch.setitem(chord_ml.CHORDMINI, model_id, (architecture,name,len(weight),sha))
    (code / 'checkpoints' / name).write_bytes(weight)
    (code / 'checkpoints' / 'other.pt').touch()
    loader = code / 'src/models/common/checkpoint_loading.py'
    loader.parent.mkdir(parents=True)
    loader.write_text('checkpoint = torch.load(path, weights_only=False)\n'
                      'def load():\n    try:\n        model.load_state_dict(state_dict)\n'
                      '    except RuntimeError:\n        model.load_state_dict(state_dict, strict=False)\n'
                      '    info(f"Loaded {path}")\n')
    monkeypatch.setattr(chord_ml, '_require_safe_btc_torch', lambda: None)
    def probe(folder, model, inputs, output, *, probe):
        assert folder == code and model == model_id and probe and (inputs / 'probe.wav').is_file()
        output.mkdir()
        (output / 'probe.lab').write_text('0 2 C:maj\n')
    monkeypatch.setattr(chord_ml, '_run_chordmini', probe)
    assert chord_ml._stage_chordmini(code, tmp_path, model_id) == hashlib.sha256(weight).hexdigest()
    assert 'weights_only=True' in loader.read_text() and 'strict=True' in loader.read_text()
    assert 'strict=False' not in loader.read_text() and not (code / 'checkpoints').exists()
