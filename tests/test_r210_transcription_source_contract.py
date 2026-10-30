"""Actual Python imports/bytecode attacks; fixture code is not a neural model."""
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path
import py_compile
import sys
from types import ModuleType

import pytest

from app import transcription_source_contract as contracts, model_license_policy as policy, auth
from test_r210_execution_entry_acceptance import api, audio
from test_r210_queue_identity_stem_metering import env as env  # noqa: F401


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path / 'runtime'
    path = root / 'source/mta_fixture_transcriber/recognizer.py'
    path.parent.mkdir(parents=True)
    path.write_text('VALUE = "approved"\n')
    files = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()}
    contract = {'files': files.copy(), 'import_roots': ['source']}
    monkeypatch.setattr(contracts, 'profile', lambda family: contract)
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'auth')
    return root, path, files


def test_validated_source_imports_namespace_and_can_repeat_without_inheriting_modules(source):
    root, _, files = source
    for _ in range(2):
        with contracts.imports(root, files, 'fixture', 'mta-analysis'):
            module = importlib.import_module('mta_fixture_transcriber.recognizer')
            assert module.VALUE == 'approved'
        assert not any(n.startswith('mta_fixture_transcriber') for n in sys.modules)


def test_rewriting_receipt_hash_cannot_authorize_different_source(source):
    root, path, files = source
    path.write_text('VALUE = "injected"\n')
    files = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()}
    with pytest.raises(ValueError, match='installed loader contract'):
        contracts.verify_sources(root, files, 'fixture')


@pytest.mark.parametrize('extra', ['other.py', 'other.pyc', 'extension.so', 'extension.pyd', 'other/__init__.py'])
def test_uninventoried_import_code_is_refused_even_when_added_to_receipt(source, extra):
    root, _, files = source
    path = root / 'source' / extra
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_bytes(b'not approved')
    files = {**files, path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()}
    with pytest.raises(ValueError, match='Uninventoried'):
        contracts.verify_sources(root, files, 'fixture')


def test_matching_timestamp_size_pyc_is_not_loaded(source):
    root, path, files = source
    original = path.read_bytes()
    stamp = path.stat()
    malicious = b'VALUE = "injected"\n'
    assert len(original) == len(malicious)
    path.write_bytes(malicious)
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    py_compile.compile(str(path), doraise=True)
    path.write_bytes(original)
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    with contracts.imports(root, files, 'fixture', 'mta-analysis'):
        assert importlib.import_module('mta_fixture_transcriber.recognizer').VALUE == 'approved'


def test_replacement_between_inventory_and_actual_import_is_rejected(source):
    root, path, files = source
    with contracts.imports(root, files, 'fixture', 'mta-analysis'):
        path.write_text('VALUE = "injected"\n')
        with pytest.raises(ValueError, match='integrity'):
            importlib.import_module('mta_fixture_transcriber.recognizer')
    assert 'mta_fixture_transcriber.recognizer' not in sys.modules


def test_cached_module_cannot_claim_approved_filename(source, monkeypatch):
    root, path, files = source
    module = ModuleType('mta_fixture_transcriber.recognizer')
    module.__file__ = str(path)
    module.VALUE = 'injected'
    monkeypatch.setitem(sys.modules, module.__name__, module)
    with pytest.raises(ValueError, match='already loaded'):
        with contracts.imports(root, files, 'fixture', 'mta-analysis'):
            pytest.fail('Poisoned namespace admitted')


def test_policy_revocation_before_actual_import_is_enforced(source, monkeypatch, tmp_path):
    root, _, files = source
    license_path = tmp_path / 'policy.json'
    monkeypatch.setattr(policy, '_path', lambda: license_path)
    with contracts.imports(root, files, 'fixture', 'mta-analysis'):
        license_path.write_text('{"mta-analysis":{"mode":"disabled"}}')
        with pytest.raises(policy.LicenseDenied):
            importlib.import_module('mta_fixture_transcriber.recognizer')


@pytest.mark.parametrize('damage', ['parent-link', 'source-link', 'hardlink'])
def test_aliases_cannot_disguise_upstream_code(source, tmp_path, damage):
    root, path, files = source
    if damage == 'parent-link':
        parent = path.parent
        moved = root / 'original'
        parent.rename(moved)
        parent.symlink_to(moved, target_is_directory=True)
    elif damage == 'source-link':
        original = path.with_suffix('.original')
        path.rename(original)
        path.symlink_to(original)
    else:
        os.link(path, tmp_path / 'external-alias.py')
    with pytest.raises(ValueError):
        contracts.verify_sources(root, files, 'fixture')


def test_unknown_module_inside_owned_namespace_does_not_fall_through(source):
    root, _, files = source
    with contracts.imports(root, files, 'fixture', 'mta-analysis'):
        with pytest.raises(ImportError, match='outside the approved'):
            importlib.import_module('mta_fixture_transcriber.unreviewed')


def test_deployment_contract_matches_historical_pinned_sources_and_only_known_yourmt3_patches():
    root = Path(__file__).resolve().parents[1]
    original = json.loads((root / 'app/studio_assets/yourmt3_sources.json').read_text())
    expected = contracts.profile('yourmt3')['files']
    assert [r['path'] for r in original['files'] if expected[r['path']] != r['sha256']] == [
        'amt/src/model/t5mod.py', 'model_helper.py']
    assert hashlib.sha256((root / 'app/studio_assets/yourmt3_t5_compat.py').read_bytes()).hexdigest() == expected['amt/src/model/mta_t5_compat.py']


def test_deployment_contract_itself_cannot_be_replaced(tmp_path, monkeypatch):
    replacement = tmp_path / 'contracts.json'
    replacement.write_text('{"schema":"mta-transcription-sources-1","profiles":{}}')
    monkeypatch.setattr(contracts, 'CONTRACT_FILE', replacement)
    with pytest.raises(ValueError, match='integrity'):
        contracts.profile('mrmt3')


def test_receipt_duplicate_fields_are_not_accepted(tmp_path):
    path = tmp_path / 'receipt.json'
    path.write_text('{"files":{},"files":{"code.py":"fake"}}')
    with pytest.raises(ValueError, match='Duplicate'):
        contracts.read_json(path)


def test_regular_packages_and_relative_imports_keep_standard_python_semantics(source, monkeypatch):
    root, path, files = source
    package = path.with_name('__init__.py')
    package.write_text('from .recognizer import VALUE\n')
    expected = {**files, package.relative_to(root).as_posix(): hashlib.sha256(package.read_bytes()).hexdigest()}
    monkeypatch.setattr(contracts, 'profile', lambda family: {'files': expected, 'import_roots': ['source']})
    with contracts.imports(root, expected, 'fixture', 'mta-analysis'):
        assert importlib.import_module('mta_fixture_transcriber').VALUE == 'approved'


@pytest.fixture
def tensor_backend(source, monkeypatch):
    root, _, _ = source
    weight = root / 'weights/model.safetensors'
    weight.parent.mkdir()
    weight.write_bytes(b'synthetic tensor snapshot')
    digest = hashlib.sha256(weight.read_bytes()).hexdigest()
    expected = {'weights/model.safetensors': digest}
    monkeypatch.setattr(contracts, 'profile', lambda family: {'checkpoints': {'fixture-model': expected}})
    parent = ModuleType('safetensors')
    backend = ModuleType('safetensors.torch')
    parent.torch = backend
    backend.load_file = lambda *a, **k: pytest.fail('Reopened a verified checkpoint pathname')
    monkeypatch.setitem(sys.modules, 'safetensors', parent)
    monkeypatch.setitem(sys.modules, 'safetensors.torch', backend)
    return root, weight, expected, backend


def test_upstream_tensor_loader_uses_snapshot_even_if_path_is_replaced(tensor_backend):
    root, weight, files, backend = tensor_backend
    original_loader = backend.load_file
    captured = []
    def load(data):
        weight.write_bytes(b'changed after verified snapshot')
        captured.append(data)
        return {'weight': 'synthetic decoded tensors'}
    backend.load = load
    with contracts.tensor_loader(root, files, 'yourmt3', 'fixture-model'):
        assert backend.load_file(str(weight)) == {'weight': 'synthetic decoded tensors'}
    assert captured == [b'synthetic tensor snapshot'] and backend.load_file is original_loader


def test_tensor_replacement_and_receipt_rewrite_do_not_change_deployment_identity(tensor_backend):
    root, weight, files, backend = tensor_backend
    backend.load = lambda _: pytest.fail('Unapproved tensor bytes decoded')
    weight.write_bytes(b'changed model')
    rewritten = {'weights/model.safetensors': hashlib.sha256(weight.read_bytes()).hexdigest()}
    with contracts.tensor_loader(root, rewritten, 'yourmt3', 'fixture-model'):
        with pytest.raises(ValueError, match='identity changed'):
            backend.load_file(str(weight))
    with contracts.tensor_loader(root, files, 'yourmt3', 'fixture-model'):
        with pytest.raises(ValueError, match='integrity'):
            backend.load_file(str(weight))


def test_explicit_gpu_placement_is_preserved_for_tensor_snapshot(tensor_backend):
    root, weight, files, backend = tensor_backend
    moves = []
    class Tensor:
        def to(self, device):
            moves.append(device)
            return self
    backend.load = lambda _: {'weight': Tensor()}
    with contracts.tensor_loader(root, files, 'yourmt3', 'fixture-model'):
        assert 'weight' in backend.load_file(str(weight), device='cuda:0')
    assert moves == ['cuda:0']


def test_unpinned_ps_variant_is_refused_before_runtime_or_model_import(tmp_path, monkeypatch):
    from app import yourmt3_adapter
    monkeypatch.setenv('MTA_STUDIO_YOURMT3_RUNTIME', str(tmp_path))
    monkeypatch.setenv('MTA_STUDIO_YOURMT3_VARIANT', 'ps')
    files = contracts.profile('yourmt3')['files'].copy()
    files['amt/logs/2024/ps/checkpoints/model.safetensors'] = '0' * 64
    (tmp_path / 'mta-runtime-ps.json').write_text(json.dumps({'model': yourmt3_adapter.selected_variant()[0],
        'commit': '5e66c1ea173a8186e0d20432b841d3180cc015b5', 'files': files, 'tested': True}))
    with pytest.raises(ValueError, match='variant has no independent tensor identity'):
        yourmt3_adapter.verified_runtime()


def test_resumable_cli_cannot_bypass_runtime_contract_with_a_different_model(tmp_path, monkeypatch):
    from app import mrmt3_adapter
    from scripts import run_mrmt3_resumable as resumable
    from model_rights_fixtures import authorize_fixture
    authorize_fixture(monkeypatch, tmp_path, 'mr-mt3-assets')
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    receipt = {'schema': 'mta-mrmt3-runtime-1', 'model': mrmt3_adapter.MODEL,
               'source_commit': mrmt3_adapter.SOURCE_COMMIT, 'tested': True,
               'files': {**contracts.profile('mrmt3')['files'], mrmt3_adapter.WEIGHTS: '0' * 64}}
    (runtime / 'mta-runtime.json').write_text(json.dumps(receipt))
    monkeypatch.setenv('MTA_STUDIO_MRMT3_RUNTIME', str(runtime))
    source = tmp_path / 'source.wav'
    source.write_bytes(audio())
    checkpoint = tmp_path / 'another.safetensors'
    checkpoint.write_bytes(b'another model')
    with pytest.raises(ValueError, match='checkpoint integrity'):
        resumable.main(['--audio', str(source), '--model', str(checkpoint), '--output', str(tmp_path / 'out')])
    assert not (tmp_path / 'out').exists()


def test_resumable_cli_requires_exact_checkpoint_after_valid_runtime_preflight(tmp_path, monkeypatch):
    from scripts import run_mrmt3_resumable as resumable
    from test_r210_mrmt3_runtime import runtime
    from model_rights_fixtures import authorize_fixture
    # Independent synthetic source contract; no injected inference or subprocess.
    runtime(tmp_path, monkeypatch)
    authorize_fixture(monkeypatch, tmp_path, 'mr-mt3-assets')
    source = tmp_path / 'source.wav'
    source.write_bytes(audio())
    checkpoint = tmp_path / 'another.safetensors'
    checkpoint.write_bytes(b'another model')
    with pytest.raises(ValueError, match='original installed checkpoint'):
        resumable.main(['--audio', str(source), '--model', str(checkpoint), '--output', str(tmp_path / 'out')])
    assert not (tmp_path / 'out').exists()


@pytest.mark.parametrize('family,kind', [('yourmt3', 'audio-to-midi-yourmt3'), ('mrmt3', 'audio-to-midi-mr-mt3')])
@pytest.mark.parametrize('transport', ['json', 'upload'])
def test_actual_token_api_rejects_self_authorized_upstream_before_process_and_ledger(env, tmp_path, monkeypatch, family, kind, transport):
    from app import ai_access, mrmt3_adapter, yourmt3_adapter
    from model_rights_fixtures import authorize_fixture
    authorize_fixture(monkeypatch, tmp_path, 'yourmt3' if family == 'yourmt3' else 'mr-mt3-assets')
    runtime = tmp_path / 'unreviewed-runtime'
    runtime.mkdir()
    files = {n: '0' * 64 for n in contracts.profile(family)['files']}
    if family == 'yourmt3':
        files['amt/logs/2024/' + yourmt3_adapter.EXPERIMENT + '/checkpoints/model.safetensors'] = '0' * 64
        receipt = {'model': yourmt3_adapter.MODEL, 'commit': '5e66c1ea173a8186e0d20432b841d3180cc015b5', 'tested': True, 'files': files}
        variable = 'MTA_STUDIO_YOURMT3_RUNTIME'
        monkeypatch.setenv('MTA_STUDIO_YOURMT3_VARIANT', 'nops')
        monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_PYTHON', sys.executable)
    else:
        files[mrmt3_adapter.WEIGHTS] = '0' * 64
        receipt = {'schema': 'mta-mrmt3-runtime-1', 'model': mrmt3_adapter.MODEL,
                   'source_commit': mrmt3_adapter.SOURCE_COMMIT, 'tested': True, 'files': files}
        variable = 'MTA_STUDIO_MRMT3_RUNTIME'
    (runtime / 'mta-runtime.json').write_text(json.dumps(receipt))
    monkeypatch.setenv(variable, str(runtime))
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.delenv('MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_EXECUTABLE', raising=False)
    token = ai_access.issue(env, 'Untrusted upstream refusal')
    headers = {'Authorization': 'Bearer ' + token['token']}
    with api() as client:
        if transport == 'json':
            response = client.post('/api/ai-jobs/execute', json={'kind': kind, 'plan': {}}, headers=headers)
        else:
            headers.update({'Content-Type': 'audio/wav', 'X-MTA-AI-Options': base64.urlsafe_b64encode(b'{}').decode()})
            response = client.post('/api/ai-jobs/execute-audio/' + kind, content=audio(), headers=headers)
    assert response.status_code == 503, response.text
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0] == 0
