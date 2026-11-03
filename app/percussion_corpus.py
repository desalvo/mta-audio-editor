"""Deterministic original diagnostic audio and honest missing real-data slots.

The procedural signals are test surrogates, not acoustic instrument recordings.
No external dataset or pretrained model is downloaded or represented as cleared.
"""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import struct
import tempfile

import numpy as np
import soundfile as sf

DATASET_ID = 'mta-synthetic-v1'
CORPUS_VERSION = 'mta-percussion-corpus-1'
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
SYNTHETIC_CASES = (
    ('conga-snare', 'Congas surrogate with simultaneous snare', 'conga_snare', ('snare',)),
    ('bongo-tom', 'Bongos surrogate with tom', 'bongo_tom', ('tom',)),
    ('shaker-hihat', 'Shaker surrogate with hi-hat', 'shaker_hihat', ('hi_hat',)),
    ('tambourine-crash', 'Tambourine surrogate with crash', 'tambourine_crash', ('cymbals',)),
    ('cowbell-ride', 'Cowbell surrogate with ride', 'cowbell_ride', ('cymbals',)),
    ('maracas-cymbals', 'Maracas surrogate with cymbals', 'maracas_cymbals', ('cymbals',)),
    ('timbales-tom', 'Timbales surrogate with floor tom', 'timbales_tom', ('tom',)),
    ('multiple-overlap', 'Overlapping accessory surrogates, original mix recovery', 'multiple_percussions', ('snare', 'hi_hat', 'tom')),
    ('kick-accessory', 'Kick concurrent with accessory percussion', 'kick_percussion', ('kick', 'snare')),
    ('stereo-distribution', 'Stereo source distribution', 'stereo', ('snare', 'hi_hat')),
    ('dynamic-range', 'Weak accessory and strong kit', 'dynamics', ('snare', 'tom')),
    ('reverb-tail', 'Long decay and reverberant surrogates', 'reverb', ('cymbals', 'snare')),
)
DIFFICULT_CASES = (
    ('no-accessory', 'Kit without accessory percussion or kick', 'negative_no_percussion', ('snare', 'tom', 'hi_hat', 'cymbals')),
    ('accessory-only', 'Accessory-only surrogate', 'accessory_only', ()),
    ('digital-silence', 'Digital silence', 'negative_silence', ()),
    ('very-short', 'Short source excerpt', 'short_audio', ('snare',)),
    ('electronic-fast', 'Dense electronic surrogate', 'electronic', ('kick', 'snare', 'hi_hat')),
    ('stereo-antiphase', 'Opposing stereo polarity stress case', 'phase', ('tom',)),
)
REAL_CASES = (
    ('real-acoustic', 'Acoustic multitrack', 'acoustic'),
    ('real-electronic', 'Electronic multitrack', 'electronic'),
    ('real-long-song', 'Long recording', 'long_audio'),
    ('real-reverb', 'Real room tails', 'reverb'),
    ('real-kick-clap', 'Kick, clap and ambiguous percussion', 'ambiguous_categories'),
    ('real-heldout-mix', 'Held-out complete song and DRUMS', 'original_mix'),
)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(root, value):
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('Invalid corpus path')
    parts = PurePosixPath(value)
    if parts.is_absolute() or any(not p or p in ('..', '.') for p in value.split('/')) or len(parts.parts) > 8:
        raise ValueError('Corpus path must remain relative')
    root = Path(root)
    if root.is_symlink():
        raise ValueError('Corpus root must not be a symlink')
    candidate = root
    for part in parts.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError('Corpus path must not include symlinks')
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError('Corpus path escapes the dataset')
    return candidate


def _tone(kind, length, rate, rng, event_number):
    t = np.arange(length, dtype=np.float64) / rate
    noise = rng.normal(0, 1, length)
    if kind in ('hi_hat', 'cymbals'):
        high = noise - np.concatenate(([0], noise[:-1]))
        return high * np.exp(-t / (.12 if kind == 'hi_hat' else .55)) * .17
    if kind == 'snare':
        return (.22 * noise + .22 * np.sin(2 * np.pi * 185 * t)) * np.exp(-t / .07)
    if kind == 'tom':
        return .5 * np.sin(2 * np.pi * (100 * t + 40 * t * np.exp(-t / .03))) * np.exp(-t / .18)
    if kind == 'kick':
        phase = 2 * np.pi * (48 * t + 22 * .025 * (1 - np.exp(-t / .025)))
        return .6 * np.sin(phase) * np.exp(-t / .09)
    # Original deterministic surrogate; this is not a conga/bongo sample library.
    frequency = 340 + (event_number % 5) * 137
    return (.35 * np.sin(2 * np.pi * frequency * t) + .18 * np.sin(2 * np.pi * frequency * 1.51 * t)
            + .04 * noise) * np.exp(-t / .09)


def _component(kind, frames, rate, rng, index, dense=False):
    data = np.zeros((frames, 2), dtype=np.float64)
    interval = .20 if dense else .64
    times = np.arange(.08, max(.09, frames / rate - .15), interval)
    for number, when in enumerate(times):
        # Every other event coincides with excluded sources; others are independent.
        offset = 0 if number % 2 == 0 or kind == 'percussion' else .07
        first = int((when + offset) * rate)
        size = min(frames - first, int(rate * (.9 if kind == 'cymbals' else .45)))
        if size <= 0:
            continue
        sound = _tone(kind, size, rate, rng, index + number)
        pan = -.65 if kind == 'percussion' else .55 if kind in ('snare', 'tom') else 0
        gains = (math.sqrt((1 - pan) / 2), math.sqrt((1 + pan) / 2))
        data[first:first + size] += sound[:, None] * gains
    return data


def _write_case(root, specification, index, seed, duration_seconds, group):
    cid, title, category, components = specification
    rate = 48000 if index % 2 else 44100
    channels = 2 if index % 3 == 0 or category in ('stereo', 'phase') else 1
    duration = min(duration_seconds, .35) if category == 'short_audio' else duration_seconds
    frames = int(round(duration * rate))
    rng = np.random.Generator(np.random.PCG64(seed + index * 1009))
    silence = category in ('negative_no_percussion', 'negative_silence')
    percussion = np.zeros((frames, 2)) if silence else _component('percussion', frames, rate, rng, index,
                                                                dense=category == 'electronic')
    parts = {kind: _component(kind, frames, rate, rng, index + n, dense=category == 'electronic')
             for n, kind in enumerate(components)}
    if category == 'dynamics':
        percussion *= .025
    if category == 'phase':
        percussion[:, 1] = -percussion[:, 0]
    if category == 'reverb':
        original = percussion.copy()
        for delay, gain in ((.07, .45), (.14, .25), (.28, .14), (.49, .08)):
            amount = int(delay * rate)
            if amount < frames:
                percussion[amount:] += original[:-amount] * gain
    full_percussion = percussion.copy()
    # Deliberately missing accessory energy in DRUMS has a separate mix reference.
    if category == 'multiple_percussions':
        percussion *= .65
    drums = percussion + sum(parts.values(), np.zeros_like(percussion))
    other = np.zeros_like(percussion)
    if category == 'multiple_percussions':
        t = np.arange(frames) / rate
        other += (.025 * np.sin(2 * np.pi * 220 * t))[:, None]
    mixture = drums + full_percussion - percussion + other
    kick = parts.get('kick', np.zeros_like(percussion))
    candidates = [drums, mixture, percussion + kick, full_percussion + kick, *parts.values()]
    maximum = max(float(np.abs(v).max(initial=0)) for v in candidates)
    gain = min(1, .8 / maximum) if maximum else 1.0
    if channels == 1:
        convert = lambda data: np.mean(data, axis=1, keepdims=True) * gain
    else:
        convert = lambda data: data * gain
    folder = root / 'cases' / cid
    folder.mkdir(parents=True)
    files = {
        'input_drums.wav': drums, 'input_mix.wav': mixture,
        'reference_include_kick.wav': percussion + kick, 'reference_exclude_kick.wav': percussion,
        'reference_mix_include_kick.wav': full_percussion + kick, 'reference_mix_exclude_kick.wav': full_percussion,
        'percussion.wav': percussion, **{kind + '.wav': data for kind, data in parts.items()},
    }
    hashes = {}
    for name, data in files.items():
        path = folder / name
        samples = np.asarray(convert(data), dtype='<f4')
        payload = samples.tobytes()
        # libsndfile FLOAT WAV adds a timestamped PEAK chunk. A fixed IEEE-float
        # RIFF header keeps the corpus byte-reproducible across separate runs.
        header = (b'RIFF' + struct.pack('<I', 36 + len(payload)) + b'WAVEfmt ' +
                  struct.pack('<IHHIIHH', 16, 3, channels, rate, rate * channels * 4, channels * 4, 32) +
                  b'data' + struct.pack('<I', len(payload)))
        path.write_bytes(header + payload)
        hashes[path.relative_to(root).as_posix()] = sha256(path)
    path_for = lambda name: (folder / name).relative_to(root).as_posix()
    return {'id': cid, 'title': title, 'category': category, 'group': group, 'prepared': True,
            'data_origin': 'original_procedural_surrogate', 'exact_ground_truth': True,
            'duration_seconds': frames / rate, 'sample_rate': rate, 'channels': channels,
            'frames': frames, 'seed': seed + index * 1009, 'family_id': cid,
            'split': 'test', 'derivations_must_remain_in_split': True,
            'input_drums': path_for('input_drums.wav'), 'input_mix': path_for('input_mix.wav'),
            'reference': path_for('reference_include_kick.wav'),
            'references': {'include_kick': path_for('reference_include_kick.wav'), 'exclude_kick': path_for('reference_exclude_kick.wav')},
            'mix_references': {'include_kick': path_for('reference_mix_include_kick.wav'), 'exclude_kick': path_for('reference_mix_exclude_kick.wav')},
            'sources': {'percussion': path_for('percussion.wav'), **{kind: path_for(kind + '.wav') for kind in parts}},
            'event_description': 'Procedural onsets coincide on alternating beats; compare exact registered component signals.',
            'critical_excerpt': {'start': 0, 'end': min(20, frames / rate)},
            'sha256': hashes}


def generate(root: Path, seed=42, duration_seconds=12):
    """Create one immutable, repeatable dataset at root; no third-party audio."""
    root = Path(root)
    if type(seed) is not int or not 0 <= seed <= 2 ** 31 - 1:
        raise ValueError('Invalid corpus seed')
    if type(duration_seconds) not in (int, float) or not math.isfinite(duration_seconds) or not .1 <= duration_seconds <= 30:
        raise ValueError('Corpus duration must be between 0.1 and 30 seconds')
    if root.exists() or root.is_symlink():
        manifest = load(root)
        if manifest.get('seed') != seed or manifest.get('duration_seconds') != duration_seconds:
            raise ValueError('Dataset version already exists with different seed/duration')
        return manifest
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.mta-corpus-', dir=root.parent) as temporary:
        temporary = Path(temporary)
        cases = [_write_case(temporary, spec, index, seed, duration_seconds, 'synthetic')
                 for index, spec in enumerate(SYNTHETIC_CASES)]
        cases += [_write_case(temporary, spec, 12 + index, seed, duration_seconds, 'negative')
                  for index, spec in enumerate(DIFFICULT_CASES)]
        for cid, title, category in REAL_CASES:
            cases.append({'id': cid, 'title': title, 'category': category, 'group': 'real', 'prepared': False,
                          'data_origin': None, 'exact_ground_truth': False, 'family_id': cid, 'split': 'test',
                          'unavailable_reason': 'Real recording and isolated sources with reviewed rights not supplied',
                          'input_drums': None, 'input_mix': None, 'reference': None, 'references': {}, 'mix_references': {},
                          'sources': {}, 'sha256': {}})
        manifest = {'schema': CORPUS_VERSION, 'id': DATASET_ID, 'name': 'MTA original diagnostic corpus v1',
                    'seed': seed, 'duration_seconds': duration_seconds, 'generator': 'NumPy PCG64 + procedural damped/noise signals',
                    'numpy_version': np.__version__, 'soundfile_version': sf.__version__,
                    'license': {'id': 'EUPL-1.2', 'source': 'Original procedural audio generated by the MTA project',
                                'third_party_audio': False, 'redistribution_allowed': True},
                    'counts': {'declared': 24, 'prepared': 18, 'synthetic': 12, 'negative': 6, 'real': 0, 'real_unavailable': 6},
                    'limits': ['Instrument names identify controlled surrogate tests, not acoustic recordings.',
                               'Six realistic slots are unavailable and cannot count toward release coverage.',
                               'No external dataset rights or training-data isolation is inferred.'],
                    'external_dataset_candidates': [
                        {'name': 'FreePats World Percussion', 'status': 'not_imported_rights_and_isolated_sources_review_required'},
                        {'name': 'WaivOps WRLD-LP', 'status': 'not_imported_rights_and_isolated_sources_review_required'},
                        {'name': 'Expanded Groove MIDI Dataset', 'status': 'not_imported_MIDI_is_not_isolated_audio_ground_truth'},
                    ], 'cases': cases}
        encoded = json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False).encode() + b'\n'
        (temporary / 'manifest.json').write_bytes(encoded)
        # Rename a prepared child: TemporaryDirectory must still clean its own root.
        staged = temporary / 'published'
        staged.mkdir()
        for child in list(temporary.iterdir()):
            if child != staged:
                child.rename(staged / child.name)
        os.rename(staged, root)
    return validate(root, manifest)


def validate(root, manifest):
    if not isinstance(manifest, dict) or manifest.get('schema') != CORPUS_VERSION or not isinstance(manifest.get('cases'), list):
        raise ValueError('Invalid corpus manifest')
    if not 1 <= len(manifest['cases']) <= 512:
        raise ValueError('Invalid corpus case count')
    seen, family_splits = set(), {}
    for case in manifest['cases']:
        if (not isinstance(case, dict) or not isinstance(case.get('id'), str)
                or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', case['id']) or case['id'] in seen
                or type(case.get('prepared')) is not bool or case.get('group') not in ('synthetic', 'real', 'negative')):
            raise ValueError('Invalid or duplicate corpus case')
        seen.add(case['id'])
        family, split = case.get('family_id'), case.get('split')
        if not isinstance(family, str) or not family or split not in ('train', 'validation', 'test'):
            raise ValueError('Corpus requires explicit family/split provenance')
        if family in family_splits and family_splits[family] != split:
            raise ValueError('Related recordings cannot cross corpus splits')
        family_splits[family] = split
        if not case.get('prepared'):
            if any(case.get(key) for key in ('input_drums', 'input_mix', 'reference', 'references', 'mix_references', 'sources', 'sha256')):
                raise ValueError('Unavailable cases cannot advertise prepared audio')
            continue
        if not isinstance(case.get('input_drums'), str):
            raise ValueError('Prepared corpus case requires an input')
        for mapping in ('references', 'mix_references', 'sources'):
            if not isinstance(case.get(mapping, {}), dict) or len(case.get(mapping, {})) > 32:
                raise ValueError('Invalid corpus source mapping')
        references = [case.get('input_drums'), case.get('input_mix'), case.get('reference'),
                      *case.get('references', {}).values(), *case.get('mix_references', {}).values(),
                      *case.get('sources', {}).values()]
        hashes = case.get('sha256')
        if not isinstance(hashes, dict) or not 1 <= len(hashes) <= 96 or not references or any(not isinstance(value, str) or value not in hashes for value in references if value is not None):
            raise ValueError('Corpus audio lacks registered hashes')
        for name, digest in hashes.items():
            path = safe_path(root, name)
            if not path.is_file() or not isinstance(digest, str) or sha256(path) != digest:
                raise ValueError('Corpus audio is missing or its SHA-256 changed')
            info = sf.info(path)
            if info.frames != case.get('frames') or info.samplerate != case.get('sample_rate') or info.channels != case.get('channels'):
                raise ValueError('Corpus audio geometry changed')
    counts = manifest.get('counts', {})
    expected_counts = {
        'declared': len(manifest['cases']),
        'prepared': sum(case['prepared'] for case in manifest['cases']),
        'synthetic': sum(case['prepared'] and case['group'] == 'synthetic' for case in manifest['cases']),
        'negative': sum(case['prepared'] and case['group'] == 'negative' for case in manifest['cases']),
        'real': sum(case['prepared'] and case['group'] == 'real' for case in manifest['cases']),
        'real_unavailable': sum(not case['prepared'] and case['group'] == 'real' for case in manifest['cases']),
    }
    if any(counts.get(key) != value for key, value in expected_counts.items()):
        raise ValueError('Corpus coverage counts do not match its registered files')
    return manifest


def load(root):
    root = Path(root)
    manifest_path = safe_path(root, 'manifest.json')
    if not manifest_path.is_file() or manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError('Corpus manifest unavailable or oversized')
    return validate(root, json.loads(manifest_path.read_text()))

