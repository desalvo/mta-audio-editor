"""Reference-based separation diagnostics; never a professional-quality approval.

Ratios which are undefined (silence or exact zero error) are JSON null, accompanied
by an explicit state. Alignment and onset estimates are diagnostics, not a claim
that an arbitrary recording has labelled acoustic instrument events.
"""
from pathlib import Path
import math

import numpy as np
import soundfile as sf
from scipy import signal

METRIC_VERSION = 'mta-percussion-metrics-1'
MAX_DECODED_SAMPLES = 16_000_000
CRITERIA = {
    'version': METRIC_VERSION,
    'integrity': 'Readable finite audio, unchanged frames/sample rate/channels, no newly saturated samples; reliable detected lag/drift must be within one sample.',
    'lag_search_ms': 250,
    'lag_confidence_min': 0.5,
    'onset_frame_ms': 5,
    'onset_match_ms': 20,
    'onset_relative_floor': 0.03,
    'quality_thresholds': None,
    'professional_acceptance': 'Requires separately recorded explicit human approval of the exact model, pipeline, options and audio hashes.',
    'limits': 'Onset and discontinuity measures are frozen engineering heuristics, not recognised professional-quality standards. Correlated sources may make bleed attribution non-identifiable.',
}


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Audio must be a regular file')
    info = sf.info(path)
    if not 0 < info.frames or not 1 <= info.channels <= 8 or not 8000 <= info.samplerate <= 192000:
        raise ValueError('Unsupported audio geometry')
    if info.frames * info.channels > MAX_DECODED_SAMPLES:
        raise ValueError('Audio exceeds bounded metric working set; split into registered excerpts')
    data, rate = sf.read(path, dtype='float64', always_2d=True)
    if np.isfinite(data).all() and np.max(np.abs(data), initial=0) > 1_000_000:
        raise ValueError('Audio sample amplitude exceeds bounded metric arithmetic')
    return data, rate, info


def _energy(value):
    return float(np.sum(np.square(value)))


def _ratio(numerator, denominator):
    value = float(numerator / denominator) if denominator > 0 else None
    return value if value is not None and math.isfinite(value) else None


def _square(value):
    return float(value * value) if abs(value) <= math.sqrt(np.finfo(float).max) else None


def _db(numerator, denominator):
    if numerator <= 0 or denominator <= 0:
        return None
    return float(10 * (math.log10(numerator) - math.log10(denominator)))


def _similarity(a, b):
    denominator = math.sqrt(_energy(a) * _energy(b))
    return float(np.clip(np.sum(a * b) / denominator, -1, 1)) if denominator > 0 else None


def _sdr(output, reference, scale_invariant=False):
    reference = reference - np.mean(reference, axis=0) if scale_invariant else reference
    output = output - np.mean(output, axis=0) if scale_invariant else output
    energy = _energy(reference)
    if energy <= np.finfo(float).tiny:
        return {'db': None, 'state': 'silent_reference'}
    target = reference * float(np.sum(output * reference) / energy) if scale_invariant else reference
    if _energy(target) <= np.finfo(float).tiny:
        return {'db': None, 'state': 'no_recovered_target'}
    noise = _energy(output - target)
    if noise <= np.finfo(float).eps ** 2 * max(energy, 1):
        return {'db': None, 'state': 'perfect_reconstruction'}
    return {'db': _db(_energy(target), noise), 'state': 'finite'}


def _lag(reference, output, rate):
    """Positive samples mean a delayed output; refine a bounded FFT estimate."""
    if not reference.size or _energy(reference) == 0 or _energy(output) == 0:
        return {'samples': None, 'ms': None, 'confidence': None}
    stride = max(1, int(math.ceil(rate / 8000)))
    a = signal.resample_poly(reference, 1, stride)
    b = signal.resample_poly(output, 1, stride)
    a -= a.mean(); b -= b.mean()
    if _energy(a) <= np.finfo(float).tiny or _energy(b) <= np.finfo(float).tiny:
        return {'samples': None, 'ms': None, 'confidence': None}
    corr = signal.correlate(b, a, method='fft')
    middle = len(a) - 1
    limit = min(int(rate * CRITERIA['lag_search_ms'] / 1000 / stride), len(a) - 1)
    region = corr[middle - limit:middle + limit + 1]
    coarse = int(np.argmax(np.abs(region))) - limit
    candidates = range(coarse * stride - stride, coarse * stride + stride + 1)
    best, score = 0, -1.0
    for offset in candidates:
        if abs(offset) >= len(reference):
            continue
        if offset >= 0:
            x, y = reference[:len(reference) - offset or None], output[offset:]
        else:
            x, y = reference[-offset:], output[:len(output) + offset]
        similarity = _similarity(x, y)
        if similarity is not None and abs(similarity) > score:
            best, score = offset, abs(similarity)
    return {'samples': int(best), 'ms': float(best * 1000 / rate), 'confidence': float(max(0, score))}


def _onsets(data, rate):
    mono = np.max(np.abs(data), axis=1)
    frame = max(1, int(round(rate * CRITERIA['onset_frame_ms'] / 1000)))
    padded = np.pad(mono, (0, (-len(mono)) % frame))
    envelope = np.sqrt(np.mean(padded.reshape(-1, frame) ** 2, axis=1))
    novelty = np.maximum(0, np.diff(envelope, prepend=0))
    maximum = float(novelty.max(initial=0))
    if maximum == 0:
        return np.array([], dtype=np.int64)
    med = float(np.median(novelty)); mad = float(np.median(np.abs(novelty - med)))
    threshold = max(maximum * CRITERIA['onset_relative_floor'], med + 6 * mad)
    peaks, _ = signal.find_peaks(np.pad(novelty, (1, 1)), height=threshold,
                                 distance=max(1, int(round(20 / CRITERIA['onset_frame_ms']))))
    return ((peaks - 1) * frame).astype(np.int64)


def _transients(output, reference, rate):
    expected, actual = _onsets(reference, rate), _onsets(output, rate)
    tolerance = int(rate * CRITERIA['onset_match_ms'] / 1000)
    available = set(range(len(actual))); matched = []
    for point in expected:
        possible = [i for i in available if abs(int(actual[i]) - int(point)) <= tolerance]
        if possible:
            index = min(possible, key=lambda i: abs(int(actual[i]) - int(point)))
            available.remove(index); matched.append((int(point), int(actual[index])))
    attack, rise_errors = [], []
    def rise_time(data):
        curve = np.max(np.abs(data), axis=1)
        peak = float(curve.max(initial=0))
        if peak <= 0:
            return None
        leading = curve[:int(np.argmax(curve)) + 1]
        low = np.flatnonzero(leading >= .1 * peak)
        high = np.flatnonzero(leading >= .9 * peak)
        return float((int(high[0]) - int(low[0])) * 1000 / rate) if len(low) and len(high) else None
    tail_error, tail_reference = 0.0, 0.0
    for first, second in matched:
        start = max(0, first - int(rate * .01)); end = min(len(reference), first + int(rate * .05))
        expected_peak = float(np.max(np.abs(reference[start:end]), initial=0))
        actual_peak = float(np.max(np.abs(output[start:end]), initial=0))
        attack.append(actual_peak - expected_peak)
        expected_rise = rise_time(reference[start:end]); actual_rise = rise_time(output[start:end])
        if expected_rise is not None and actual_rise is not None:
            rise_errors.append(actual_rise - expected_rise)
        tail_start = first + int(rate * .05); tail_end = min(len(reference), first + int(rate * .25))
        if tail_end > tail_start:
            tail_reference += _energy(reference[tail_start:tail_end])
            tail_error += _energy(output[tail_start:tail_end] - reference[tail_start:tail_end])
    shifts = [(b - a) * 1000 / rate for a, b in matched]
    return {'method': '5ms positive RMS-envelope novelty; engineering heuristic',
            'reference_events': len(expected), 'output_events': len(actual), 'matched_events': len(matched),
            'lost_events': len(expected) - len(matched), 'spurious_events': len(available),
            'shifted_matched_events': sum(a != b for a, b in matched),
            'mean_absolute_shift_ms': float(np.mean(np.abs(shifts))) if shifts else None,
            'peak_difference_mean': float(np.mean(attack)) if attack else None,
            'peak_difference_absolute_mean': float(np.mean(np.abs(attack))) if attack else None,
            'attack_rise_error_ms_mean': float(np.mean(rise_errors)) if rise_errors else None,
            'tail_error_energy_ratio': _ratio(tail_error, tail_reference),
            'matching_tolerance_ms': CRITERIA['onset_match_ms']}


def _bleed(output, reference, sources, geometry):
    reference_energy = _energy(reference)
    vectors = [reference.reshape(-1)] if reference_energy > 0 else []
    source_offset = len(vectors)
    names, excluded = [], []
    decoded = 0
    for name, path in sorted((sources or {}).items()):
        if name in ('percussion', 'percussions', 'accessory_percussion', 'target'):
            continue
        decoded += output.size
        if decoded > MAX_DECODED_SAMPLES:
            raise ValueError('Interference references exceed bounded metric working set; use registered excerpts')
        data, rate, _ = _read(path)
        if (data.shape, rate) != geometry or not np.isfinite(data).all():
            raise ValueError('Interference reference geometry or samples invalid: ' + name)
        if _energy(data) > 0:
            names.append(name); excluded.append(data.reshape(-1))
    if not excluded:
        return {}, None
    vectors.extend(excluded)
    gram = np.array([[float(np.dot(a, b)) for b in vectors] for a in vectors])
    coefficients = np.linalg.lstsq(gram, np.array([np.dot(v, output.reshape(-1)) for v in vectors]), rcond=None)[0]
    rank = int(np.linalg.matrix_rank(gram))
    identifiable = rank == len(vectors)
    energies = [_square(float(coefficients[i + source_offset]) * math.sqrt(float(gram[i + source_offset, i + source_offset]))) for i in range(len(names))]
    values = {name: {'gain_estimate': float(coefficients[i + source_offset]),
                     'projected_energy': energies[i],
                     'projected_energy_ratio_to_target': _ratio(energies[i], reference_energy) if energies[i] is not None else None,
                     'identifiable': identifiable}
              for i, name in enumerate(names)}
    return values, 'Source projections are not identifiable because references are correlated' if not identifiable else None


def analyze(output: Path, input_path: Path, reference: Path | None = None, sources: dict | None = None):
    """Inspect unchanged output bytes; never align, resample or level-match metrics."""
    warnings = []
    try:
        estimate, rate, info = _read(output)
        mixture, source_rate, source_info = _read(input_path)
    except (ValueError, RuntimeError, OSError) as exc:
        return {'metric_version': METRIC_VERSION, 'technical_pass': False,
                'technical': {'readable': False, 'error': str(exc)}, 'quality': {}, 'transients': {}, 'warnings': []}
    finite = bool(np.isfinite(estimate).all())
    same_geometry = bool(estimate.shape == mixture.shape and rate == source_rate)
    technical = {'readable': True, 'finite': finite, 'frames': int(info.frames), 'sample_rate': int(rate),
                 'channels': int(info.channels), 'duration_seconds': float(info.duration),
                 'input_frames': int(source_info.frames), 'duration_preserved': info.frames == source_info.frames,
                 'sample_rate_preserved': rate == source_rate, 'channels_preserved': info.channels == source_info.channels,
                 'geometry_preserved': same_geometry}
    result = {'metric_version': METRIC_VERSION, 'technical_pass': finite and same_geometry,
              'technical': technical, 'quality': {}, 'transients': {}, 'warnings': warnings}
    if not finite or not np.isfinite(mixture).all():
        result['technical_pass'] = False
        technical['input_finite'] = bool(np.isfinite(mixture).all())
        return result
    if not same_geometry:
        warnings.append('Metrics require matching geometry; no automatic resampling or cropping was applied')
        return result
    # PCM integer saturation can occur one least-significant bit below +1.
    def saturated(data, subtype):
        bits = {'PCM_16': 16, 'PCM_24': 24, 'PCM_32': 32, 'PCM_U8': 8}.get(subtype)
        threshold = 1 - 2 ** (1 - bits) if bits else 1.0
        return np.abs(data) >= threshold
    clipping = saturated(estimate, info.subtype)
    introduced = clipping & ~saturated(mixture, source_info.subtype)
    technical.update(peak=float(np.max(np.abs(estimate))), clipped_samples=int(np.count_nonzero(clipping)),
                     introduced_clipped_samples=int(np.count_nonzero(introduced)),
                     rms=float(np.sqrt(np.mean(estimate ** 2))))
    if introduced.any():
        result['technical_pass'] = False
    jumps = np.max(np.abs(np.diff(estimate, axis=0)), axis=1) if len(estimate) > 1 else np.array([])
    input_jumps = np.max(np.abs(np.diff(mixture, axis=0)), axis=1) if len(mixture) > 1 else np.array([])
    technical['maximum_sample_jump'] = float(jumps.max(initial=0))
    technical['input_maximum_sample_jump'] = float(input_jumps.max(initial=0))
    technical['discontinuity_review_required'] = bool(technical['maximum_sample_jump'] > max(.25, 4 * technical['input_maximum_sample_jump']))
    if technical['discontinuity_review_required']:
        warnings.append('New large sample jump detected; inspect waveform (heuristic, not automatic quality rejection)')
    if reference is None:
        warnings.append('No exact ground truth: objective separation/transient quality is unavailable; human listening required')
        return result
    try:
        target, target_rate, _ = _read(reference)
        if target.shape != estimate.shape or target_rate != rate or not np.isfinite(target).all():
            raise ValueError('Ground truth geometry or samples invalid')
    except (ValueError, RuntimeError, OSError) as exc:
        technical['reference_valid'] = False; warnings.append(str(exc)); result['technical_pass'] = False
        return result
    technical['reference_valid'] = True
    desired_energy = _energy(target)
    recovered_gain = float(np.sum(estimate * target) / desired_energy) if desired_energy > 0 else None
    recovered_ratio = _square(recovered_gain) if recovered_gain is not None else None
    sdr = _sdr(estimate, target)
    sisdr = _sdr(estimate, target, True)
    baseline = _sdr(mixture, target, True)
    quality = {'sdr_db': sdr['db'], 'sdr_state': sdr['state'], 'si_sdr_db': sisdr['db'], 'si_sdr_state': sisdr['state'],
               'input_si_sdr_db': baseline['db'], 'input_si_sdr_state': baseline['state'],
               'si_sdr_improvement_db': sisdr['db'] - baseline['db'] if sisdr['db'] is not None and baseline['db'] is not None else None,
               'temporal_correlation': _similarity(estimate, target), 'desired_gain_estimate': recovered_gain,
               'desired_energy_recovered_ratio': recovered_ratio,
               'useful_energy_loss_ratio': max(0, 1 - recovered_ratio) if recovered_ratio is not None else None,
               'error_energy': _energy(estimate - target), 'output_energy': _energy(estimate),
               'reference_energy': desired_energy, 'silent_target': desired_energy == 0,
               'spurious_output_energy': _energy(estimate) if desired_energy == 0 else None,
               'spurious_output_rms': float(np.sqrt(np.mean(estimate ** 2))) if desired_energy == 0 else None}
    quality['per_channel'] = [{
        'channel': ch, 'correlation': _similarity(estimate[:, ch], target[:, ch]),
        'energy_ratio': _ratio(_energy(estimate[:, ch]), _energy(target[:, ch])),
    } for ch in range(estimate.shape[1])]
    if estimate.shape[1] == 2:
        quality['stereo_side_error_ratio'] = _ratio(_energy((estimate[:, 0] - estimate[:, 1]) - (target[:, 0] - target[:, 1])),
                                                   _energy(target[:, 0] - target[:, 1]))
        quality['interchannel_correlation_error'] = None
        actual = _similarity(estimate[:, 0], estimate[:, 1]); expected = _similarity(target[:, 0], target[:, 1])
        if actual is not None and expected is not None:
            quality['interchannel_correlation_error'] = actual - expected
    try:
        quality['bleed'], bleed_warning = _bleed(estimate, target, sources, (estimate.shape, rate))
        if bleed_warning:
            warnings.append(bleed_warning)
    except (ValueError, RuntimeError, OSError) as exc:
        quality['bleed'] = {}; warnings.append(str(exc)); result['technical_pass'] = False
    channel = int(np.argmax(np.sum(target ** 2, axis=0)))
    mono_target, mono_estimate = target[:, channel], estimate[:, channel]
    alignment = _lag(mono_target, mono_estimate, rate)
    technical['alignment'] = alignment
    half = len(target) // 2
    early = _lag(mono_target[:half], mono_estimate[:half], rate)
    late = _lag(mono_target[half:], mono_estimate[half:], rate)
    reliable = lambda value: value['samples'] is not None and value['confidence'] >= CRITERIA['lag_confidence_min']
    drift = late['samples'] - early['samples'] if reliable(early) and reliable(late) else None
    technical['drift_samples'] = drift
    technical['alignment_verified'] = reliable(alignment)
    technical['drift_verified'] = drift is not None
    technical['polarity_reversed'] = quality['temporal_correlation'] is not None and quality['temporal_correlation'] < -.5
    if technical['polarity_reversed']:
        result['technical_pass'] = False
    if reliable(alignment) and abs(alignment['samples']) > 1 or drift is not None and abs(drift) > 1:
        result['technical_pass'] = False
    if not reliable(alignment) or drift is None:
        warnings.append('Alignment/drift could not be verified from a sufficiently correlated target; no absence of drift is claimed')
    result['quality'] = quality
    result['transients'] = _transients(estimate, target, rate)
    return result

