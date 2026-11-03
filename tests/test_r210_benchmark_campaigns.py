"""Campaign integrity with synthetic fixtures, never actual neural/human approval.

The six 'real' metadata records below simulate administrator-uploaded claims
for testing acceptance logic. Their audio remains procedural fixture data.
"""
import copy
import io
import json
from pathlib import Path
import shutil
import zipfile

import pytest

from app import auth, ai_arranger_runtime as queue
from app import percussion_adapters as adapters, percussion_benchmark as bench, percussion_corpus as corpus


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'authority')
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'queue')
    monkeypatch.setattr(adapters, '_activation_path', lambda: tmp_path / 'activation.json')
    monkeypatch.setattr('app.model_license_policy.evaluate_model', lambda model: None)
    dataset_root = bench.root() / 'datasets' / 'mta-synthetic-v1'
    manifest = corpus.generate(dataset_root, duration_seconds=.1)
    # Simulate distinct uploaded recording declarations for gate tests only.
    cases = manifest['cases'][:18]
    for index in range(6):
        case = copy.deepcopy(cases[index])
        case.update(id='real-fixture-' + str(index), group='real', family_id='recording-fixture-' + str(index),
                    data_origin='synthetic_test_fixture_only',
                    rights={'basis': 'user_owned', 'source': 'Test-only simulated administrator declaration'})
        cases.append(case)
    manifest['cases'] = cases
    manifest['counts'].update(declared=24, prepared=24, real=6, real_unavailable=0)
    (dataset_root / 'manifest.json').write_text(json.dumps(manifest))
    original_catalog = adapters.catalog

    def model_catalog():
        value = original_catalog()
        value['models'][0]['status'] = {'state': 'ready', 'ready': True, 'reason': 'Synthetic contract fixture'}
        return value

    monkeypatch.setattr(adapters, 'catalog', model_catalog)
    monkeypatch.setattr(adapters, 'verify_installation', lambda request: {'fixture': 'no real checkpoint'})
    calls = []

    def fixture_inference(request, source, output_dir, **kwargs):
        calls.append(request.as_dict())
        reference_name = 'reference_' + ('mix_' if request.source_mode == 'mix' else '') + ('include_kick' if request.include_kick else 'exclude_kick') + '.wav'
        output = Path(output_dir) / 'fixture_output.wav'
        shutil.copyfile(Path(source).parent / reference_name, output)
        return {'output': output, 'components': {'percussion': output}, 'raw_components': {'percussion': output},
                'inference_completed': True, 'model_version': request.model_version,
                'checkpoint_sha256': request.checkpoint_sha256, 'profile_sha256': request.profile_sha256,
                'execution_profile': {'fixture': 'not actual neural inference'}, 'format_conversions': []}

    monkeypatch.setattr(adapters, 'infer', fixture_inference)
    return dataset_root, calls


def campaign(environment, **options):
    response = bench.create({'kind': 'release', 'model_ids': ['mvsep-mega53'],
                             'dataset_ids': ['mta-synthetic-v1'], 'options': options}, 7)
    return response['campaign']['id']


@pytest.fixture
def completed(environment):
    cid = campaign(environment, source_mode='drums')
    result = bench.run(cid, 7)
    assert result['counts']['completed'] == 24 if 'counts' in result else result['campaign']['counts']['completed'] == 24
    return cid


def rate_all(cid, *, explicit=True):
    value = bench._read(cid)
    for row in value['results']:
        bench.rate(cid, {'case_id': row['case_id'], 'candidate_id': row['candidate_id'],
                         'scores': {key: 5 for key in bench.SCORES}, 'decision': 'professional',
                         'explicit_approval': explicit, 'comment': 'Synthetic gate fixture, not a human assessment'}, 7)


def test_both_sources_have_distinct_cases_references_and_frozen_checkpoint(environment):
    cid = campaign(environment)
    value = bench._read(cid)
    assert len(value['config']['cases']) == 48
    assert {case['source_mode'] for case in value['config']['cases']} == {'drums', 'mix'}
    case = next(case for case in value['config']['cases'] if case['id'] == 'multiple-overlap' and case['source_mode'] == 'mix')
    reference = bench._reference(case, bench._case_options(value, case))
    assert reference.name == 'reference_mix_include_kick.wav'
    assert value['config']['models'][0]['checkpoint_sha256'] == adapters.prepare_request().checkpoint_sha256


def test_unavailable_models_never_become_inference_or_approval(environment, monkeypatch):
    cid = campaign(environment, source_mode='drums')
    original = adapters.catalog
    def unavailable():
        value = original(); value['models'][0]['status'] = {'state': 'not_installed', 'ready': False}
        return value
    monkeypatch.setattr(adapters, 'catalog', unavailable)
    result = bench.start(cid, 7)
    assert result['campaign']['counts']['completed'] == 0
    assert result['campaign']['counts']['not_installed'] == 24
    assert not environment[1]
    assert not result['approval']['can_approve']


def test_actual_completed_fixture_is_reused_only_while_all_bytes_are_unchanged(completed, environment):
    calls = len(environment[1])
    bench.run(completed, 7)
    assert len(environment[1]) == calls
    value = bench._read(completed)
    row = value['results'][0]
    assert bench._verified_result(completed, row)
    assert row['source_bindings'] and row['files'] and row['request']['pipeline_sha256']
    assert row['inference_completed'] is True


@pytest.mark.parametrize('role', ['input', 'reference', 'component'])
def test_changed_source_reference_or_component_cannot_be_rated_or_approved(completed, environment, role):
    value = bench._read(completed); row = value['results'][0]
    if role == 'component':
        path = bench.folder(completed) / next(iter(row['files']))
    else:
        binding = row['source_bindings'][role]
        path = bench.root() / 'datasets' / binding['dataset_id'] / binding['relative']
    with path.open('ab') as stream:
        stream.write(b'changed fixture bytes')
    assert not bench._verified_result(completed, row)
    assert bench.get(completed)['campaign']['counts']['completed'] < 24
    assert not bench.approval(value)['can_approve']
    with pytest.raises(ValueError, match='missing, invalid or changed'):
        bench.rate(completed, {'case_id': row['case_id'], 'candidate_id': row['candidate_id'],
                   'scores': {key: 5 for key in bench.SCORES}, 'decision': 'professional'}, 7)


def test_final_approval_requires_explicit_ratings_and_is_invalidated_by_edit(completed):
    rate_all(completed, explicit=False)
    assert not bench.approval(bench._read(completed))['can_approve']
    rate_all(completed)
    value = bench._read(completed)
    assert bench.approval(value)['can_approve']
    approved = bench.approve(completed, {'confirm': True, 'configuration_sha256': value['config_sha256']}, 7)
    assert approved['approval']['approved']
    row = value['results'][0]
    bench.rate(completed, {'case_id': row['case_id'], 'candidate_id': row['candidate_id'],
               'scores': {key: 4 for key in bench.SCORES}, 'decision': 'limited'}, 7)
    assert not bench.approval(bench._read(completed))['approved']


@pytest.mark.parametrize('problem', ['one_family', 'missing_family', 'duplicate_audio'])
def test_real_recording_variants_never_inflate_family_coverage(environment, problem):
    cid = campaign(environment)
    value = bench._read(cid)
    real = [case for case in value['config']['cases'] if case['group'] == 'real']
    for case in real:
        if problem == 'one_family': case['family_id'] = 'same-original-recording'
        elif problem == 'missing_family': case.pop('family_id', None)
        else: case['sha256'][case['input_drums']] = '0' * 64
    value['config_sha256'] = bench.json_hash(value['config'])
    bench._write(bench.folder(cid) / 'campaign.json', value)
    assert any('Six distinct real recording families' in reason for reason in bench.approval(value)['blocked_reasons'])


def test_restored_claims_and_ratings_are_historical_never_active_approval(completed, monkeypatch, tmp_path):
    rate_all(completed)
    value = bench._read(completed)
    bench.approve(completed, {'confirm': True, 'configuration_sha256': value['config_sha256']}, 7)
    data = bench.export(completed)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert any(name.startswith('source_audio/') for name in archive.namelist())
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'restored-authority')
    result = bench.restore(data, 9)
    restored = bench._read(completed)
    assert restored['actor_user_id'] == 9 and restored['ratings'] == []
    assert restored['imported_ratings'] and restored['restoration']['claims_verified'] is False
    assert 'manual_approval' not in restored
    assert not result['approval']['can_approve'] and not result['approval']['approved']
    assert all(row['status'] == 'imported_unverified' and not row['inference_completed'] for row in restored['results'])


@pytest.mark.parametrize('limit', ['compressed', 'expanded', 'files'])
def test_archive_limits_fail_before_publication(environment, monkeypatch, limit):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('campaign.json', b'x' * 1000)
    data = stream.getvalue()
    if limit == 'compressed': monkeypatch.setattr(bench, 'MAX_ARCHIVE_BYTES', len(data) - 1)
    elif limit == 'expanded': monkeypatch.setattr(bench, 'MAX_ARCHIVE_BYTES', 999)
    else: monkeypatch.setattr(bench, 'MAX_FILES', 0)
    with pytest.raises(ValueError): bench.restore(data, 7)
    assert not (bench.root() / 'campaigns').exists()
