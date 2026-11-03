"""Adapter contract/integrity fixtures, never real neural quality acceptance."""
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import threading

import numpy as np
import pytest
import soundfile as sf

from app import main, mega53_runtime, model_license_policy
from app import percussion_adapters as adapters


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(adapters, '_activation_path', lambda: tmp_path / 'activation.json')
    monkeypatch.setattr(model_license_policy, 'evaluate_model', lambda model: None)
    return tmp_path


def audio(path, value=.1, frames=4410, rate=44100, channels=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.full((frames, channels), value), rate, subtype='FLOAT')
    return path


def wav_bytes(value=.1, frames=4410, rate=44100, channels=2):
    with io.BytesIO() as stream:
        sf.write(stream, np.full((frames, channels), value), rate, format='WAV', subtype='FLOAT')
        return stream.getvalue()


def test_complete_candidate_catalog_never_implies_available_models(fixture):
    data = adapters.catalog()
    assert data['no_automatic_downloads']
    models = {item['id']: item for item in data['models']}
    assert len(models) == 11
    assert models['mvsep-mega53']['adapter_implemented']
    assert not any(item['adapter_implemented'] for key, item in models.items() if key != 'mvsep-mega53')
    assert all(not item['status']['ready'] for item in models.values())
    assert models['separate-and-detect']['status']['state'] == 'incompatible'
    assert models['audiosep-hive']['checkpoint_sha256'] == 'a13fff5fa4ece1a8bc13e42e1c7b8d90e21603075302ca89e4339c9471973300'
    assert all(item['checkpoint_sha256'] is None or len(item['checkpoint_sha256']) == 64 for item in models.values())


@pytest.mark.parametrize('model', [item['id'] for item in adapters._metadata()['models'] if item['id'] != 'mvsep-mega53'])
def test_unreviewed_candidates_cannot_run_or_activate(fixture, model):
    with pytest.raises(adapters.AdapterUnavailable):
        adapters.prepare_request(model)
    with pytest.raises(adapters.AdapterUnavailable, match='Unreviewed'):
        adapters.configure_enabled([model])
    assert not (fixture / 'activation.json').exists()


def test_profile_hash_is_pinned_and_serializable(fixture):
    request = adapters.prepare_request()
    assert request.include_kick and request.clap == request.timpani == 'exclude'
    assert json.loads(json.dumps(request.as_dict())) == request.as_dict()
    assert request.checkpoint_sha256 == mega53_runtime.MEGA53_V1_SHA256
    assert adapters.prepare_request(options={'include_kick': False}).profile_sha256 != request.profile_sha256
    assert adapters.prepare_request(options={'source_mode': 'mix'}).profile_sha256 != request.profile_sha256
    assert request == adapters.prepare_request()


def test_catalog_metadata_cannot_create_a_new_executable_adapter(fixture, monkeypatch):
    metadata = adapters._metadata()
    candidate = metadata['models'][1]
    candidate.update(adapter_implemented=True, weights_permission_verified=True, enabled_by_default=True)
    monkeypatch.setattr(adapters, '_metadata', lambda: metadata)
    with pytest.raises(adapters.AdapterUnavailable, match='No executable adapter'):
        adapters.prepare_request(candidate['id'])
    with pytest.raises(adapters.AdapterUnavailable, match='Unreviewed'):
        adapters.configure_enabled([candidate['id']])
    assert adapters.model_status(candidate)['state'] == 'incompatible'


@pytest.mark.parametrize('options', [[], {'command': 'python custom.py'}, {'include_kick': 'true'},
                                   {'clap': 'guess'}, {'timpani': 'auto'}, {'source_mode': 'other'}])
def test_invalid_options_are_rejected_before_effects(fixture, options):
    with pytest.raises(ValueError):
        adapters.prepare_request(options=options)
    assert not list(fixture.iterdir())


@pytest.mark.parametrize('category', ['clap', 'timpani'])
def test_unavailable_category_is_not_silently_substituted(fixture, category):
    with pytest.raises(adapters.AdapterUnavailable, match='cannot independently'):
        adapters.prepare_request(options={category: 'include'})


def test_model_activation_is_persistent_and_does_not_override_rights(fixture, monkeypatch):
    adapters.configure_enabled([])
    assert adapters.enabled_models() == []
    with pytest.raises(adapters.AdapterUnavailable, match='disabled'):
        adapters.prepare_request()
    adapters.configure_enabled(['mvsep-mega53'])

    def denied(model):
        raise model_license_policy.LicenseDenied('fixture revoked')

    monkeypatch.setattr(model_license_policy, 'evaluate_model', denied)
    assert adapters.catalog()['models'][0]['status']['state'] == 'not_authorized'


@pytest.mark.parametrize('value', [{}, {'schema': 'bad', 'enabled_models': []},
                                  {'schema': 'mta-percussion-activation-1', 'enabled_models': ['unknown']}])
def test_damaged_activation_file_fails_closed(fixture, value):
    (fixture / 'activation.json').write_text(json.dumps(value))
    with pytest.raises(ValueError):
        adapters.enabled_models()


def test_installation_verification_is_exact_and_never_downloads(fixture, monkeypatch):
    for key in ('MTA_MEGA53_ROOT', 'MTA_MEGA53_CONFIG', 'MTA_MEGA53_CHECKPOINT'):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(adapters.AdapterUnavailable) as result:
        adapters.verify()
    assert result.value.state == 'not_installed'
    (fixture / 'inference.py').write_text('# synthetic identity fixture\n')
    config = fixture / 'config.yaml'; config.write_text('fixture: true\n')
    checkpoint = fixture / 'weights.ckpt'; checkpoint.write_bytes(b'not the actual neural weights')
    for key, value in [('MTA_MEGA53_ROOT', fixture), ('MTA_MEGA53_CONFIG', config), ('MTA_MEGA53_CHECKPOINT', checkpoint)]:
        monkeypatch.setenv(key, str(value))
    with pytest.raises(adapters.AdapterUnavailable, match='SHA-256 mismatch'):
        adapters.verify()
    monkeypatch.setattr(mega53_runtime, 'verify_mega53_checkpoint', lambda path: Path(path))
    with pytest.raises(adapters.AdapterUnavailable, match='identity differs'):
        adapters.verify()


@pytest.mark.parametrize('include_kick', [False, True])
def test_registered_server_path_preserves_components_and_pcm(fixture, monkeypatch, include_kick):
    from app import ai_server_execution
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, '_ai_external_engine', lambda kind: True)
    identities, calls = [], []
    monkeypatch.setattr(ai_server_execution, 'identity', lambda: identities.append('active-durable-owner'))
    source = audio(fixture / 'input.wav')
    raw_percussion = wav_bytes(.1)

    def infer(kind, path, plan):
        calls.append((kind, path, plan))
        return {'audio': {'percussions.wav': raw_percussion, **({'kick.wav': wav_bytes(.2)} if include_kick else {})}}, 'registered-job'

    monkeypatch.setattr(main, '_native_remote_infer', infer)
    request = adapters.prepare_request(options={'include_kick': include_kick})
    result = adapters.infer(request, source, fixture / 'out')
    assert identities == ['active-durable-owner'] and calls[0][0] == 'drumsep'
    assert calls[0][2] == {'model': 'mvsep-mega53', 'targets': ['percussion', *(['kick'] if include_kick else [])]}
    data, rate = sf.read(result['output'], always_2d=True)
    np.testing.assert_allclose(data, .3 if include_kick else .1, atol=1e-7)
    assert rate == 44100 and data.shape == (4410, 2)
    assert result['raw_components']['percussion'].read_bytes() == raw_percussion
    assert result['worker_job_id'] == 'registered-job'
    assert result['manual_validation_status'] == 'In attesa di validazione umana'


def test_unowned_server_execution_is_rejected_before_dispatch_or_output(fixture, monkeypatch):
    from app import ai_server_execution
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, '_ai_external_engine', lambda kind: True)

    def denied():
        raise ValueError('Authenticated active global AI job required')

    monkeypatch.setattr(ai_server_execution, 'identity', denied)
    monkeypatch.setattr(main, '_native_remote_infer', lambda *a: pytest.fail('Unowned inference must not dispatch'))
    source = audio(fixture / 'input.wav')
    with pytest.raises(ValueError, match='active global'):
        adapters.infer(adapters.prepare_request(), source, fixture / 'out')
    assert not (fixture / 'out').exists()


def test_native_is_the_only_direct_execution_route(fixture, monkeypatch):
    monkeypatch.setattr(main, '_ai_external_engine', lambda kind: False)
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(mega53_runtime, 'infer_drums', lambda *a, **k: pytest.fail('Unowned direct route'))
    with pytest.raises(adapters.AdapterUnavailable, match='native'):
        adapters.infer(adapters.prepare_request(), audio(fixture / 'input.wav'), fixture / 'out')


@pytest.mark.parametrize('problem', ['clipping', 'nan', 'duration', 'missing', 'extra', 'stereo_loss'])
def test_invalid_model_outputs_never_become_success(fixture, monkeypatch, problem):
    from app import ai_server_execution
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, '_ai_external_engine', lambda kind: True)
    monkeypatch.setattr(ai_server_execution, 'identity', lambda: 1)
    source = audio(fixture / 'input.wav')
    data = {'percussions.wav': wav_bytes(.8 if problem == 'clipping' else (float('nan') if problem == 'nan' else .1)),
            'kick.wav': wav_bytes(.8 if problem == 'clipping' else .1)}
    if problem == 'duration':
        data['percussions.wav'] = wav_bytes(frames=4000)
    elif problem == 'missing':
        data.pop('kick.wav')
    elif problem == 'extra':
        data['snare.wav'] = wav_bytes()
    elif problem == 'stereo_loss':
        data['percussions.wav'] = wav_bytes(channels=1)
    monkeypatch.setattr(main, '_native_remote_infer', lambda *a, **k: ({'audio': data}, 'job'))
    with pytest.raises(adapters.AdapterUnavailable) as result:
        adapters.infer(adapters.prepare_request(), source, fixture / 'out')
    assert result.value.state == 'invalid_result'
    assert not (fixture / 'out/percussion_output.wav').exists()


def test_explicit_mix_input_and_format_conversion_preserve_original_components(fixture, monkeypatch):
    from app import ai_server_execution
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, '_ai_external_engine', lambda kind: True)
    monkeypatch.setattr(ai_server_execution, 'identity', lambda: 1)
    drums = audio(fixture / 'drums.wav')
    mix = audio(fixture / 'mix.wav', frames=4800, rate=48000, channels=1)
    raw = wav_bytes(.1)

    def infer(kind, path, options):
        assert path == mix
        return {'audio': {'percussions.wav': raw, 'kick.wav': raw}}, 'registered-job'

    monkeypatch.setattr(main, '_native_remote_infer', infer)
    request = adapters.prepare_request(options={'source_mode': 'mix'})
    with pytest.raises(ValueError, match='Original mix'):
        adapters.infer(request, drums, fixture / 'missing')
    result = adapters.infer(request, drums, fixture / 'out', original_mix=mix)
    assert sf.info(result['output']).samplerate == 48000
    assert sf.info(result['output']).frames == 4800
    assert sf.info(result['output']).channels == 1
    assert result['raw_components']['percussion'].read_bytes() == raw
    assert len(result['format_conversions']) == 2
    assert not any(item['gain_applied'] for item in result['format_conversions'])


def test_cancel_and_tampered_prepared_request_have_no_effects(fixture, monkeypatch):
    source = audio(fixture / 'source.wav')
    request = adapters.prepare_request()
    monkeypatch.setattr(main, '_native_remote_infer', lambda *a, **k: pytest.fail('Cancelled or stale request dispatch'))
    with pytest.raises(adapters.AdapterUnavailable, match='profile changed'):
        adapters.infer(replace(request, checkpoint_sha256='0' * 64), source, fixture / 'out')
    event = threading.Event(); event.set()
    with pytest.raises(RuntimeError, match='cancelled'):
        adapters.infer(request, source, fixture / 'out', cancel_event=event)
    assert not (fixture / 'out').exists()


def test_existing_output_is_never_reused_as_new_inference(fixture):
    source = audio(fixture / 'source.wav')
    old = fixture / 'out/percussions.wav'; audio(old)
    before = hashlib.sha256(old.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='fresh'):
        adapters.infer(adapters.prepare_request(), source, fixture / 'out')
    assert hashlib.sha256(old.read_bytes()).hexdigest() == before
