"""Real synthetic audio validates measurements, never a neural benchmark score."""
import copy
import json

import numpy as np
import pytest
import soundfile as sf

from app import percussion_corpus as corpus, percussion_metrics as metrics


def audio(path, data, rate=16000):
    sf.write(path, np.asarray(data), rate, subtype='FLOAT')
    return path


@pytest.fixture
def signals(tmp_path):
    rate = 16000
    rng = np.random.default_rng(42)
    desired = rng.normal(0, .03, (rate, 2))
    excluded = rng.normal(0, .03, (rate, 2))
    return (audio(tmp_path / 'target.wav', desired), audio(tmp_path / 'snare.wav', excluded),
            audio(tmp_path / 'mix.wav', desired + excluded), desired, excluded, rate)


def test_perfect_reference_sdr_is_explicit_and_silent_output_is_not_perfect(signals, tmp_path):
    target, snare, mixture, desired, excluded, rate = signals
    result = metrics.analyze(target, mixture, target, {'snare': snare})
    assert result['technical_pass']
    assert result['quality']['sdr_db'] is None
    assert result['quality']['sdr_state'] == result['quality']['si_sdr_state'] == 'perfect_reconstruction'
    assert result['quality']['temporal_correlation'] == pytest.approx(1)
    assert result['quality']['bleed']['snare']['projected_energy'] == pytest.approx(0, abs=1e-15)
    assert result['technical']['alignment']['samples'] == 0
    assert result['technical']['drift_samples'] == 0
    assert result['transients']['attack_rise_error_ms_mean'] == 0
    json.dumps(result, allow_nan=False)
    silent = audio(tmp_path / 'silent.wav', np.zeros_like(desired), rate)
    empty = metrics.analyze(silent, mixture, target)
    assert empty['quality']['si_sdr_state'] == 'no_recovered_target'
    assert empty['quality']['useful_energy_loss_ratio'] == 1


def test_sdr_improvement_and_individual_bleed_are_measured(signals, tmp_path):
    target, snare, mixture, desired, excluded, rate = signals
    estimate = audio(tmp_path / 'estimate.wav', desired + excluded * .2, rate)
    result = metrics.analyze(estimate, mixture, target, {'snare': snare})
    # A finite random sample is not perfectly orthogonal to the reference.
    assert result['quality']['si_sdr_improvement_db'] == pytest.approx(20 * np.log10(5), abs=.1)
    bleed = result['quality']['bleed']['snare']
    assert bleed['identifiable']
    assert bleed['gain_estimate'] == pytest.approx(.2, abs=1e-7)
    assert bleed['projected_energy_ratio_to_target'] == pytest.approx(.04, rel=.03)
    assert result['quality']['desired_gain_estimate'] == pytest.approx(1, abs=.01)
    assert result['quality']['stereo_side_error_ratio'] > 0


@pytest.mark.parametrize('failure', ['nan', 'inf', 'duration', 'rate', 'channels', 'clipping', 'lag', 'polarity'])
def test_integrity_failures_do_not_pass(signals, tmp_path, failure):
    target, snare, mixture, desired, excluded, rate = signals
    output = desired.copy()
    if failure == 'nan': output[10, 0] = np.nan
    elif failure == 'inf': output[10, 0] = np.inf
    elif failure == 'duration': output = output[:-1]
    elif failure == 'rate': rate = 48000
    elif failure == 'channels': output = output[:, 0]
    elif failure == 'clipping': output[10, 0] = 1.1
    elif failure == 'lag': output = np.concatenate((np.zeros((128, 2)), output[:-128]))
    elif failure == 'polarity': output *= -1
    path = audio(tmp_path / (failure + '.wav'), output, rate)
    result = metrics.analyze(path, mixture, target)
    assert not result['technical_pass'], result
    json.dumps(result, allow_nan=False)
    if failure == 'lag':
        assert result['technical']['alignment']['samples'] == 128
    if failure == 'polarity':
        assert result['technical']['polarity_reversed']


def test_silent_reference_has_no_invalid_ratios_and_spurious_energy_is_counted(tmp_path):
    silent = audio(tmp_path / 'silent.wav', np.zeros((16000, 1)))
    noisy = audio(tmp_path / 'noise.wav', np.random.default_rng(1).normal(0, .02, (16000, 1)))
    result = metrics.analyze(noisy, silent, silent)
    assert result['quality']['silent_target']
    assert result['quality']['si_sdr_state'] == 'silent_reference'
    assert result['quality']['spurious_output_energy'] > 0
    assert result['quality']['temporal_correlation'] is None
    assert not result['technical']['alignment_verified']
    json.dumps(result, allow_nan=False)


def test_opposing_stereo_is_not_lost_by_mono_alignment(tmp_path):
    rng = np.random.default_rng(44)
    left = rng.normal(0, .03, 16000)
    path = audio(tmp_path / 'stereo.wav', np.column_stack((left, -left)))
    result = metrics.analyze(path, path, path)
    assert result['technical_pass']
    assert result['technical']['alignment_verified']
    assert result['quality']['stereo_side_error_ratio'] == 0


def test_missing_reference_reports_unavailable_quality(signals):
    target, snare, mixture, desired, excluded, rate = signals
    result = metrics.analyze(target, mixture)
    assert result['technical_pass']
    assert not result['quality'] and not result['transients']
    assert 'No exact ground truth' in result['warnings'][0]


def test_lost_and_artificial_transients_are_reported(tmp_path):
    rate = 16000
    reference = np.zeros((rate * 2, 1)); estimate = reference.copy()
    for start in (.2, .7, 1.2):
        i = int(start * rate)
        reference[i:i + 160, 0] = np.hanning(320)[:160] * .3
    estimate[:] = reference
    estimate[int(.7 * rate):int(.7 * rate) + 160] = 0
    estimate[int(1.7 * rate):int(1.7 * rate) + 160, 0] = np.hanning(320)[:160] * .3
    target = audio(tmp_path / 'reference.wav', reference, rate)
    result = metrics.analyze(audio(tmp_path / 'estimate.wav', estimate, rate), target, target)
    assert result['transients']['reference_events'] == 3
    assert result['transients']['lost_events'] == result['transients']['spurious_events'] == 1


def test_correlated_bleed_sources_are_not_claimed_identifiable(signals):
    target, snare, mixture, desired, excluded, rate = signals
    result = metrics.analyze(mixture, mixture, target, {'snare': snare, 'tom': snare})
    assert not result['quality']['bleed']['snare']['identifiable']
    assert any('not identifiable' in message for message in result['warnings'])


def test_invalid_files_and_metric_memory_bound_fail_closed(tmp_path, monkeypatch):
    bad = tmp_path / 'bad.wav'; bad.write_bytes(b'not audio')
    result = metrics.analyze(bad, bad)
    assert not result['technical_pass'] and not result['technical']['readable']
    path = audio(tmp_path / 'ok.wav', np.ones((1000, 1)) * .01)
    monkeypatch.setattr(metrics, 'MAX_DECODED_SAMPLES', 999)
    result = metrics.analyze(path, path)
    assert not result['technical_pass'] and 'bounded metric' in result['technical']['error']


@pytest.fixture
def prepared(tmp_path):
    root = tmp_path / 'corpus'
    return root, corpus.generate(root, seed=42, duration_seconds=.2)


def test_corpus_has_eighteen_real_files_and_six_honest_missing_slots(prepared):
    root, manifest = prepared
    assert len(manifest['cases']) == 24
    available = [case for case in manifest['cases'] if case['prepared']]
    assert len(available) == 18
    assert sum(case['group'] == 'synthetic' for case in available) == 12
    assert sum(case['group'] == 'negative' for case in available) == 6
    real = [case for case in manifest['cases'] if case['group'] == 'real']
    assert len(real) == 6 and all(not case['prepared'] for case in real)
    assert manifest['license']['third_party_audio'] is False
    assert {case['sample_rate'] for case in available} == {44100, 48000}
    assert {case['channels'] for case in available} == {1, 2}
    for case in available:
        assert case['data_origin'] == 'original_procedural_surrogate'
        target = corpus.safe_path(root, case['reference'])
        result = metrics.analyze(target, corpus.safe_path(root, case['input_drums']), target,
                                 {name: corpus.safe_path(root, value) for name, value in case['sources'].items()})
        assert result['technical_pass'], (case['id'], result)
        assert result['quality']['sdr_state'] in ('perfect_reconstruction', 'silent_reference')
    assert corpus.load(root) == manifest


def test_seed_and_file_hashes_are_reproducible_and_existing_dataset_immutable(prepared, tmp_path):
    root, manifest = prepared
    again = corpus.generate(tmp_path / 'again', seed=42, duration_seconds=.2)
    assert again == manifest
    assert corpus.generate(root, seed=42, duration_seconds=.2) == manifest
    with pytest.raises(ValueError, match='different seed'):
        corpus.generate(root, seed=43, duration_seconds=.2)
    alternate = corpus.generate(tmp_path / 'alternate', seed=43, duration_seconds=.2)
    assert alternate['cases'][0]['sha256'] != manifest['cases'][0]['sha256']


@pytest.mark.parametrize('change', ['bytes', 'hash', 'path', 'split', 'unavailable'])
def test_corrupt_or_unsafe_corpus_cannot_be_reused(prepared, change):
    root, manifest = prepared
    damaged = copy.deepcopy(manifest)
    first = damaged['cases'][0]
    if change == 'bytes':
        corpus.safe_path(root, first['input_drums']).write_bytes(b'corrupt')
    elif change == 'hash':
        first['sha256'][first['input_drums']] = '0' * 64
    elif change == 'path':
        first['sha256']['../escape.wav'] = first['sha256'].pop(first['input_drums'])
        first['input_drums'] = '../escape.wav'
    elif change == 'split':
        damaged['cases'][1]['family_id'] = first['family_id']
        damaged['cases'][1]['split'] = 'train'
    else:
        damaged['cases'][-1]['input_drums'] = first['input_drums']
    with pytest.raises(ValueError):
        corpus.validate(root, damaged)


@pytest.mark.parametrize('value', ['../secret', '/absolute/secret', 'a/../secret', 'a\\secret', './secret', 'a\x00b'])
def test_corpus_paths_are_bounded(tmp_path, value):
    with pytest.raises(ValueError):
        corpus.safe_path(tmp_path, value)


def test_kick_variants_and_original_mix_recovery_have_distinct_ground_truth(tmp_path):
    root = tmp_path / 'corpus'
    manifest = corpus.generate(root, seed=42, duration_seconds=.3)
    case = next(case for case in manifest['cases'] if case['id'] == 'kick-accessory')
    include, _ = sf.read(root / case['references']['include_kick'], always_2d=True)
    exclude, _ = sf.read(root / case['references']['exclude_kick'], always_2d=True)
    kick, _ = sf.read(root / case['sources']['kick'], always_2d=True)
    assert np.allclose(include - exclude, kick, atol=2e-8)
    case = next(case for case in manifest['cases'] if case['id'] == 'multiple-overlap')
    direct, _ = sf.read(root / case['references']['exclude_kick'], always_2d=True)
    full, _ = sf.read(root / case['mix_references']['exclude_kick'], always_2d=True)
    assert np.allclose(direct, full * .65, atol=2e-8)

@pytest.mark.parametrize('kind', ['counts', 'geometry', 'symlink'])
def test_manifest_coverage_geometry_and_symlinks_are_verified(prepared, kind, tmp_path):
    root, manifest = prepared
    damaged = copy.deepcopy(manifest)
    if kind == 'counts':
        damaged['counts']['real'] = 6
    elif kind == 'geometry':
        damaged['cases'][0]['frames'] += 1
    else:
        path = root / damaged['cases'][0]['input_drums']
        outside = tmp_path / 'outside.wav'
        outside.write_bytes(path.read_bytes())
        path.unlink(); path.symlink_to(outside)
    with pytest.raises(ValueError):
        corpus.validate(root, damaged)


def test_temporal_drift_and_different_interference_geometry_are_not_accepted(signals, tmp_path):
    target, snare, mixture, desired, excluded, rate = signals
    changed = desired.copy()
    half = len(changed) // 2
    changed[half + 64:] = desired[half:-64]
    changed[half:half + 64] = 0
    result = metrics.analyze(audio(tmp_path / 'drifting.wav', changed, rate), mixture, target)
    assert not result['technical_pass']
    assert result['technical']['drift_samples'] == 64
    wrong = audio(tmp_path / 'wrong-reference.wav', excluded[:-1], rate)
    result = metrics.analyze(target, mixture, target, {'snare': wrong})
    assert not result['technical_pass']
    assert any('reference geometry' in message for message in result['warnings'])


def test_extreme_finite_amplitude_cannot_overflow_metrics(signals, tmp_path):
    target, snare, mixture, desired, excluded, rate = signals
    path = audio(tmp_path / 'enormous.wav', np.ones_like(desired) * 1e25, rate)
    result = metrics.analyze(path, mixture, target)
    assert not result['technical_pass']
    assert 'bounded metric arithmetic' in result['technical']['error']
    json.dumps(result, allow_nan=False)

