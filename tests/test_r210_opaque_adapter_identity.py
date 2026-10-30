"""Real configuration denial; no synthetic resolver injection in this module."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app import ai_adapter_identity as identity, ai_worker_registry as registry
from app import ai_worker_protocol as legacy, model_license_policy as policy, auth
from model_rights_fixtures import synthetic_review
from test_r210_execution_entry_acceptance import KINDS, api, audio
from test_r210_queue_identity_stem_metering import env as env  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def opaque(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('MTA_AI_EXECUTION_MODE', 'local')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    marker = tmp_path / 'executed'
    worker = tmp_path / 'ai_unified_adapter.py'
    worker.write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
    worker.chmod(0o700)
    return worker, marker


@pytest.mark.parametrize('kind', KINDS)
def test_each_builtin_kind_rejects_opaque_override_without_builtin_fallback(opaque, monkeypatch, kind):
    worker, marker = opaque
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_EXECUTABLE', str(worker))
    assert registry.resolve_worker(kind) is None
    assert registry.available_workers()[kind] is False
    assert not marker.exists()


@pytest.mark.parametrize('kind', KINDS)
def test_supported_kind_is_bound_to_its_own_installed_integration(monkeypatch, kind):
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    name = ('ai_studio_adapter.py' if kind in __import__('app.studio_catalog', fromlist=['KINDS']).KINDS
            else 'ai_unified_adapter.py' if kind in identity.UNIFIED_KINDS else 'ace_step_http_worker.py')
    correct = ROOT / 'app' / name
    monkeypatch.setenv('MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_EXECUTABLE', str(correct))
    assert registry.resolve_worker(kind) == correct
    for other in {'ai_unified_adapter.py', 'ai_studio_adapter.py', 'ace_step_http_worker.py'} - {name}:
        monkeypatch.setenv('MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_EXECUTABLE', str(ROOT / 'app' / other))
        assert registry.resolve_worker(kind) is None


@pytest.mark.parametrize('alias', ['copy', 'symlink', 'parent-symlink', 'hardlink'])
def test_same_name_or_even_same_bytes_do_not_authorize_external_code(tmp_path, monkeypatch, alias):
    source = ROOT / 'app/ai_unified_adapter.py'
    worker = tmp_path / source.name
    if alias == 'copy': worker.write_bytes(source.read_bytes())
    elif alias == 'symlink': worker.symlink_to(source)
    elif alias == 'hardlink': os.link(source, worker)
    else:
        (tmp_path / 'alias').symlink_to(source.parent, target_is_directory=True)
        worker = tmp_path / 'alias' / source.name
    if alias == 'copy': worker.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_WHISPER_EXECUTABLE', str(worker))
    assert registry.resolve_worker('whisper') is None


@pytest.mark.parametrize('worker_name', ['opaque', 'ai_unified_adapter.py', 'ai_studio_adapter.py'])
def test_custom_registry_cannot_grant_identity_with_labels_or_metering(opaque, tmp_path, monkeypatch, worker_name):
    runner = opaque[0] if worker_name == 'opaque' else ROOT / 'app' / worker_name
    config = tmp_path / 'registry.json'
    config.write_text(json.dumps([{'kind': 'operator-plugin', 'executable': str(runner),
        'python': sys.executable, 'label': 'Reviewed known model', 'gpu_capable': True,
        'metering_method': 'gpu-kernel-union-v1'}]))
    monkeypatch.setenv('MTA_AI_ENGINE_REGISTRY_FILE', str(config))
    assert 'operator-plugin' in registry.registered_kinds()
    assert registry.resolve_worker('operator-plugin') is None
    assert not registry.execution_available('operator-plugin')


@pytest.mark.parametrize('kind', sorted(__import__('app.studio_catalog', fromlist=['KINDS']).KINDS))
def test_extension_cannot_override_reserved_studio_kind(opaque, tmp_path, monkeypatch, kind):
    config = tmp_path / 'registry.json'
    config.write_text(json.dumps([{'kind': kind, 'executable': str(opaque[0])}]))
    monkeypatch.setenv('MTA_AI_ENGINE_REGISTRY_FILE', str(config))
    with pytest.raises(ValueError, match='duplicate'):
        registry.extensions()


@pytest.mark.parametrize('entry', ['legacy', 'project', 'probe'])
def test_legacy_configuration_never_executes_an_opaque_worker(opaque, monkeypatch, entry):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_EXECUTABLE', str(opaque[0]))
    assert legacy.configured_worker() is None
    if entry == 'probe': assert legacy.probe_worker()['probe_ok'] is False
    else:
        with pytest.raises(legacy.WorkerUnavailable):
            if entry == 'legacy': legacy.run_external_worker({})
            else: legacy.run_worker_with_project_audio({}, None, lambda *a: pytest.fail('Rejected source read'))
    assert not opaque[1].exists()


@pytest.mark.parametrize('damage', ['none', 'entry', 'sibling', 'missing', 'link', 'parent'])
def test_managed_ace_copy_requires_every_shipped_sibling(tmp_path, monkeypatch, damage):
    from app import ace_step_desktop_manager as manager
    monkeypatch.setenv('MTA_ACE_STEP_DESKTOP_DIR', str(tmp_path / 'managed'))
    manager._activate_adapter()
    worker = manager.home() / 'adapter/ace_step_http_worker.py'
    sibling = worker.with_name('ace_gpu_process_meter.py')
    if damage == 'entry': worker.write_text('raise RuntimeError("substituted")')
    elif damage == 'sibling': sibling.write_text('raise RuntimeError("substituted")')
    elif damage == 'missing': sibling.unlink()
    elif damage == 'link':
        sibling.unlink(); sibling.symlink_to(ROOT / 'app' / sibling.name)
    elif damage == 'parent':
        directory = worker.parent
        directory.rename(directory.with_name('other'))
        directory.symlink_to(directory.with_name('other'), target_is_directory=True)
    assert (legacy.configured_worker() == worker) is (damage == 'none')
    assert (registry.resolve_worker('ace-step') == worker) is (damage == 'none')


@pytest.mark.parametrize('consent', [False, True])
def test_raw_ace_launcher_denial_has_no_cache_or_process_side_effect(opaque, tmp_path, consent):
    from app.ace_step_local import launch
    cache = tmp_path / 'cache'
    with pytest.raises(policy.LicenseDenied, match='checkpoint loader contract'):
        launch(str(opaque[0]), model_dir=str(cache), confirm_download=consent)
    assert not cache.exists() and not opaque[1].exists()


def test_actual_raw_launcher_cli_cannot_bypass_with_download_consent(opaque, tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / 'app/ace_step_local.py'),
        '--executable', str(opaque[0]), '--model-dir', str(tmp_path / 'cache'), '--allow-model-download'],
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and 'checkpoint loader contract' in result.stderr
    assert not opaque[1].exists() and not (tmp_path / 'cache').exists()


def test_pinned_checkpoint_and_operator_policy_name_do_not_attest_generic_singer(opaque, tmp_path, monkeypatch):
    from app import neural_vocal_adapter
    model = tmp_path / 'checkpoint'; model.write_bytes(b'generated synthetic fixture')
    for key, value in {'EXECUTABLE': str(opaque[0]), 'CHECKPOINT': str(model),
                       'SHA256': hashlib.sha256(model.read_bytes()).hexdigest(), 'POLICY_MODEL': 'oddvoices'}.items():
        monkeypatch.setenv('MTA_NEURAL_SINGER_' + key, value)
    with pytest.raises(policy.LicenseDenied, match='checkpoint loader contract'):
        neural_vocal_adapter.checked_assets()
    with pytest.raises(policy.LicenseDenied, match='checkpoint loader contract'):
        policy.evaluate('vocal-synthesis', {'settings': {'backend': 'neural-external'}})
    assert not opaque[1].exists()


def test_direct_generic_singer_is_denied_before_score_or_output_access(opaque, tmp_path):
    from app.neural_vocal_adapter import render_neural
    with pytest.raises(policy.LicenseDenied, match='checkpoint loader contract'):
        render_neural(None, SimpleNamespace(backend='neural-external'), tmp_path / 'output',
                      lambda *a: pytest.fail('Denied singer reported progress'))
    assert not (tmp_path / 'output').exists() and not opaque[1].exists()


def test_generic_singer_executable_alone_cannot_advertise_synthesis(opaque, monkeypatch):
    from app import studio_catalog, studio_asset_registry, vocal_banks
    monkeypatch.setattr(studio_asset_registry, 'catalog', lambda: [])
    monkeypatch.setattr(vocal_banks, 'status', lambda: [])
    monkeypatch.setenv('MTA_NEURAL_SINGER_EXECUTABLE', str(opaque[0]))
    monkeypatch.delenv('MTA_DIFFSINGER_ROOT', raising=False)
    assert studio_catalog.python_for('vocal-synthesis') is None


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('transport', ['json', 'upload'])
def test_real_token_api_rejects_opaque_adapter_before_inference_or_ledger(env, opaque, tmp_path, monkeypatch, kind, transport):
    from app import ai_access
    monkeypatch.setenv('MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_EXECUTABLE', str(opaque[0]))
    plan = {}
    if kind == 'backing-vocals': plan['model'] = 'mvsep-mega53'
    if kind == 'drumsep': plan['model'] = 'dsp'
    if kind == 'chords-ml': plan['engine'] = 'profile-fast'
    if kind == 'audio-to-midi-transkun':
        from test_r210_managed_execution_identity import install_at
        install_at(tmp_path / 'models', monkeypatch)
        plan['options'] = {'asset_id': 'identity-piano'}
    model = policy.selected(kind, plan)
    license_file = tmp_path / 'synthetic-rights.json'
    license_file.write_text(json.dumps({model: synthetic_review('free_only')}))
    monkeypatch.setattr(policy, '_path', lambda: license_file)
    # Prove that permission alone would allow these synthetic fixture bytes.
    assert policy.evaluate(kind, plan).model_id == model
    token = ai_access.issue(env, 'Opaque executable rejection')
    headers = {'Authorization': 'Bearer ' + token['token']}
    with api() as client:
        if transport == 'json':
            response = client.post('/api/ai-jobs/execute', json={'kind': kind, 'plan': plan}, headers=headers)
        else:
            source, media = audio(), 'audio/wav'
            if kind in ('vocal-harmony', 'vocal-synthesis'):
                from test_r210_studio_large_remote_options import score
                source, media = score(), 'application/vnd.mta.score+json'
            headers.update({'Content-Type': media, 'X-MTA-AI-Options': base64.urlsafe_b64encode(json.dumps(plan).encode()).decode()})
            response = client.post('/api/ai-jobs/execute-audio/' + kind, content=source, headers=headers)
    assert response.status_code == 503, response.text
    assert not opaque[1].exists()
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0] == 0
