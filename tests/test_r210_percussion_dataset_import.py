"""Real WAV archives exercise provenance, identity, limits and atomic publication."""
import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import zipfile

import numpy as np
import pytest
import soundfile as sf

from app import percussion_corpus as corpus, percussion_dataset_import as imports


def wav_bytes(frames=800, rate=16000, channels=1, *, nan=False, format='WAV'):
    buffer = io.BytesIO()
    values = np.sin(np.arange(frames) * .13)[:, None] * .2
    values = np.repeat(values, channels, axis=1)
    if nan:
        values[0, 0] = np.nan
    sf.write(buffer, values, rate, format=format, subtype='FLOAT' if format == 'WAV' else 'PCM_16')
    return buffer.getvalue()


@pytest.fixture
def dataset():
    audio = wav_bytes()
    relative = 'recordings/source.wav'
    manifest = {
        'schema': corpus.CORPUS_VERSION, 'id': 'my-recordings-v1', 'name': 'User-owned recording',
        'counts': {'declared': 1, 'prepared': 1, 'synthetic': 0, 'negative': 0, 'real': 1, 'real_unavailable': 0},
        'cases': [{
            'id': 'song-one', 'title': 'My recording', 'group': 'real', 'category': 'acoustic',
            'prepared': True, 'exact_ground_truth': False, 'family_id': 'original-song-one', 'split': 'test',
            'duration_seconds': .05, 'frames': 800, 'sample_rate': 16000, 'channels': 1,
            'input_drums': relative, 'input_mix': None, 'reference': None,
            'references': {}, 'mix_references': {}, 'sources': {},
            'rights': {'basis': 'user_owned', 'source': 'Recorded and owned by the importing administrator'},
            'sha256': {relative: hashlib.sha256(audio).hexdigest()},
        }],
    }
    return manifest, {relative: audio}


def archive(manifest, files, *, extra=(), raw_manifest=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr('manifest.json', json.dumps(manifest) if raw_manifest is None else raw_manifest)
        for name, data in files.items():
            zipped.writestr(name, data)
        for name, data in extra:
            zipped.writestr(name, data)
    return buffer.getvalue()


def test_genuine_recording_import_records_authenticated_declaration_and_can_reopen(dataset, tmp_path):
    manifest, files = dataset
    manifest['import_record'] = {'actor_user_id': 666, 'professional_quality_approval': True}
    manifest['human_approval'] = True
    manifest['cases'][0]['rights']['reviewed_by'] = 666
    manifest['cases'][0]['rights']['verified'] = True
    data = archive(manifest, files)
    destination = tmp_path / manifest['id']
    imported = imports.import_archive(data, destination, 7, True)
    assert corpus.load(destination) == imported
    assert (destination / 'recordings/source.wav').read_bytes() == files['recordings/source.wav']
    assert imported['import_record']['actor_user_id'] == 7
    assert imported['import_record']['archive_sha256'] == hashlib.sha256(data).hexdigest()
    assert imported['import_record']['declaration_only'] is True
    assert imported['import_record']['automated_rights_verification'] is False
    assert imported['import_record']['professional_quality_approval'] is False
    assert 'human_approval' not in imported
    assert 'reviewed_by' not in imported['cases'][0]['rights']
    assert 'verified' not in imported['cases'][0]['rights']


@pytest.mark.parametrize('actor,acknowledge', [(0, True), (-1, True), (True, True), (1.5, True), (7, False), (7, 1), (7, None)])
def test_authenticated_actor_and_explicit_rights_ack_are_mandatory(dataset, tmp_path, actor, acknowledge):
    manifest, files = dataset
    destination = tmp_path / manifest['id']
    with pytest.raises(ValueError, match='acknowledgement'):
        imports.import_archive(archive(manifest, files), destination, actor, acknowledge)
    assert not destination.exists()


@pytest.mark.parametrize('rights', [
    None, {}, {'basis': 'unknown', 'source': 'Claimed audio'},
    {'basis': 'user_owned', 'source': ''},
    {'basis': 'licensed', 'source': 'Recorded source', 'license': 'CC-BY-4.0'},
    {'basis': 'licensed', 'source': 'Recorded source', 'evidence': 'https://example.test/license'},
])
def test_prepared_real_recordings_require_concrete_provenance(dataset, tmp_path, rights):
    manifest, files = dataset
    manifest['cases'][0]['rights'] = rights
    with pytest.raises(ValueError):
        imports.import_archive(archive(manifest, files), tmp_path / manifest['id'], 7, True)


def test_licensed_recording_preserves_recorded_permission_evidence(dataset, tmp_path):
    manifest, files = dataset
    manifest['cases'][0]['rights'] = {'basis': 'licensed', 'source': 'Owner provided isolated recording',
                                      'license': 'CC-BY-4.0', 'evidence': 'https://example.test/permission',
                                      'attribution': 'Recording author'}
    value = imports.import_archive(archive(manifest, files), tmp_path / manifest['id'], 7, True)
    assert value['cases'][0]['rights']['evidence'] == 'https://example.test/permission'
    assert value['import_record']['automated_rights_verification'] is False


@pytest.mark.parametrize('path', [
    '../escape.wav', '/absolute.wav', 'a/../escape.wav', 'a//b.wav', 'a\\b.wav', './a.wav',
    'C:/a.wav', 'CON.wav', 'a.wav ', 'folder./a.wav', 'a\u202eb.wav', 'e\u0301.wav',
])
def test_noncanonical_or_nonportable_paths_never_extract(dataset, tmp_path, path):
    manifest, files = dataset
    data = archive(manifest, files, extra=[(path, b'escape')])
    destination = tmp_path / manifest['id']
    with pytest.raises(ValueError):
        imports.import_archive(data, destination, 7, True)
    assert not destination.exists()
    assert not (tmp_path / 'escape.wav').exists()


@pytest.mark.parametrize('extra', ['unregistered.wav', 'payload.py', 'nested/manifest.json'])
def test_only_manifest_and_registered_wav_files_are_allowed(dataset, tmp_path, extra):
    manifest, files = dataset
    with pytest.raises(ValueError, match='exactly match'):
        imports.import_archive(archive(manifest, files, extra=[(extra, b'not allowed')]), tmp_path / manifest['id'], 7, True)


def test_case_colliding_and_duplicate_archive_names_are_rejected(dataset, tmp_path):
    manifest, files = dataset
    for extra in [('RECORDINGS/source.wav', next(iter(files.values()))), ('recordings/source.wav', b'duplicate')]:
        with pytest.raises(ValueError, match='colliding'):
            imports.import_archive(archive(manifest, files, extra=[extra]), tmp_path / manifest['id'], 7, True)


def test_symlinks_and_special_files_in_archive_are_rejected(dataset, tmp_path):
    manifest, files = dataset
    for mode in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR):
        special = zipfile.ZipInfo('linked.wav')
        special.create_system = 3
        special.external_attr = (mode | 0o600) << 16
        with pytest.raises(ValueError, match='link, special file'):
            imports.import_archive(archive(manifest, files, extra=[(special, b'/outside')]), tmp_path / manifest['id'], 7, True)


@pytest.mark.parametrize('failure', ['hash', 'geometry', 'counts', 'family_split', 'same_audio_split', 'nan', 'fake_wav'])
def test_corrupted_audio_geometry_and_split_leakage_fail_before_publication(dataset, tmp_path, failure):
    manifest, files = dataset
    case = manifest['cases'][0]
    if failure == 'hash':
        case['sha256']['recordings/source.wav'] = '0' * 64
    elif failure == 'geometry':
        case['frames'] = 801
    elif failure == 'counts':
        manifest['counts']['prepared'] = 2
    elif failure in ('family_split', 'same_audio_split'):
        second = copy.deepcopy(case)
        second.update(id='song-two', split='train')
        if failure == 'same_audio_split':
            second['family_id'] = 'a-different-declared-family'
        manifest['cases'].append(second)
        manifest['counts'].update(declared=2, prepared=2, real=2)
    elif failure == 'nan':
        files['recordings/source.wav'] = wav_bytes(nan=True)
        case['sha256']['recordings/source.wav'] = hashlib.sha256(files['recordings/source.wav']).hexdigest()
    else:
        files['recordings/source.wav'] = wav_bytes(format='FLAC')
        case['sha256']['recordings/source.wav'] = hashlib.sha256(files['recordings/source.wav']).hexdigest()
    destination = tmp_path / manifest['id']
    with pytest.raises(ValueError):
        imports.import_archive(archive(manifest, files), destination, 7, True)
    assert not destination.exists()


@pytest.mark.parametrize('limit', ['compressed', 'uncompressed', 'files', 'manifest'])
def test_import_resource_limits_fail_closed(dataset, tmp_path, monkeypatch, limit):
    manifest, files = dataset
    data = archive(manifest, files)
    if limit == 'compressed': monkeypatch.setattr(imports, 'MAX_COMPRESSED_BYTES', len(data) - 1)
    elif limit == 'uncompressed': monkeypatch.setattr(imports, 'MAX_UNCOMPRESSED_BYTES', 10)
    elif limit == 'files': monkeypatch.setattr(imports, 'MAX_FILES', 1)
    else: monkeypatch.setattr(corpus, 'MAX_MANIFEST_BYTES', 10)
    destination = tmp_path / manifest['id']
    with pytest.raises(ValueError):
        imports.import_archive(data, destination, 7, True)
    assert not destination.exists()


@pytest.mark.parametrize('raw', ['{"id":1,"id":2}', '{"value":NaN}', '{"value":1e999}', 'not JSON'])
def test_invalid_ambiguous_or_nonfinite_json_is_rejected(dataset, tmp_path, raw):
    manifest, files = dataset
    with pytest.raises(ValueError):
        imports.import_archive(archive(manifest, files, raw_manifest=raw), tmp_path / manifest['id'], 7, True)


@pytest.mark.parametrize('existing', ['empty', 'nonempty', 'symlink'])
def test_existing_destination_is_never_overwritten(dataset, tmp_path, existing):
    manifest, files = dataset
    destination = tmp_path / manifest['id']
    if existing == 'symlink':
        elsewhere = tmp_path / 'elsewhere'; elsewhere.mkdir()
        (elsewhere / 'keep').write_text('original')
        destination.symlink_to(elsewhere, target_is_directory=True)
    else:
        destination.mkdir()
        if existing == 'nonempty':
            (destination / 'keep').write_text('original')
    with pytest.raises(ValueError):
        imports.import_archive(archive(manifest, files), destination, 7, True)
    if existing != 'empty':
        assert (destination / 'keep').read_text() == 'original'


def test_parent_symlink_identifier_mismatch_and_prefix_collision_are_rejected(dataset, tmp_path):
    manifest, files = dataset
    alias = tmp_path / 'alias'; target = tmp_path / 'target'; target.mkdir()
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match='symlinks'):
        imports.import_archive(archive(manifest, files), alias / manifest['id'], 7, True)
    with pytest.raises(ValueError, match='identifier mismatch'):
        imports.import_archive(archive(manifest, files), tmp_path / 'other-id', 7, True)
    prefix = 'manifest.json/other.wav'
    manifest['cases'][0]['sha256'][prefix] = hashlib.sha256(next(iter(files.values()))).hexdigest()
    files[prefix] = next(iter(files.values()))
    with pytest.raises(ValueError, match='paths collide'):
        imports.import_archive(archive(manifest, files), tmp_path / manifest['id'], 7, True)


def test_publication_reserves_new_directory_and_manifest_is_last(dataset, tmp_path, monkeypatch):
    manifest, files = dataset
    destination = tmp_path / manifest['id']
    original_replace = imports.os.replace
    commits = []
    def observe(source, target):
        assert Path(target) == destination / 'manifest.json'
        assert (destination / 'recordings/source.wav').is_file()
        assert not (destination / 'manifest.json').exists()
        commits.append(True)
        return original_replace(source, target)
    monkeypatch.setattr(imports.os, 'replace', observe)
    imports.import_archive(archive(manifest, files), destination, 7, True)
    assert commits == [True]


def test_racing_existing_directory_and_publication_failure_do_not_destroy_data(dataset, tmp_path, monkeypatch):
    manifest, files = dataset
    destination = tmp_path / manifest['id']
    original_load = corpus.load
    def race(stage):
        result = original_load(stage)
        destination.mkdir()
        (destination / 'keep').write_text('another import')
        return result
    monkeypatch.setattr(corpus, 'load', race)
    with pytest.raises(ValueError, match='never overwrite'):
        imports.import_archive(archive(manifest, files), destination, 7, True)
    assert (destination / 'keep').read_text() == 'another import'


def test_failed_publication_removes_only_its_unpublished_directory(dataset, tmp_path, monkeypatch):
    manifest, files = dataset
    destination = tmp_path / manifest['id']
    def fail(*args):
        raise OSError('disk full')
    monkeypatch.setattr(imports.os, 'replace', fail)
    with pytest.raises(OSError, match='disk full'):
        imports.import_archive(archive(manifest, files), destination, 7, True)
    assert not destination.exists()
    assert not list(tmp_path.glob('.dataset-import-*'))


def test_raw_nul_name_in_central_directory_is_not_silently_truncated(dataset, tmp_path):
    manifest, files = dataset
    original = files.pop('recordings/source.wav')
    files['recordings/source.wavZ'] = original
    data = archive(manifest, files).replace(b'recordings/source.wavZ', b'recordings/source.wav\0')
    with pytest.raises(ValueError, match='original dataset archive path'):
        imports.import_archive(data, tmp_path / manifest['id'], 7, True)


def test_explicit_valid_directory_entries_are_allowed(dataset, tmp_path):
    manifest, files = dataset
    value = imports.import_archive(archive(manifest, files, extra=[('recordings/', b'')]),
                                   tmp_path / manifest['id'], 7, True)
    assert value['counts']['real'] == 1


def test_parent_changed_to_symlink_before_publication_is_rejected(dataset, tmp_path, monkeypatch):
    manifest, files = dataset
    parent = tmp_path / 'datasets'; parent.mkdir()
    elsewhere = tmp_path / 'elsewhere'; elsewhere.mkdir()
    original_load = corpus.load
    def replace_parent(stage):
        value = original_load(stage)
        parent.rename(tmp_path / 'moved-datasets')
        parent.symlink_to(elsewhere, target_is_directory=True)
        return value
    monkeypatch.setattr(corpus, 'load', replace_parent)
    with pytest.raises(ValueError, match='symlinks'):
        imports.import_archive(archive(manifest, files), parent / manifest['id'], 7, True)
    assert not (elsewhere / manifest['id']).exists()


def test_archive_identifier_is_bounded_and_selects_only_the_manifest_id(dataset, tmp_path):
    manifest, files = dataset
    assert imports.archive_identifier(archive(manifest, files)) == manifest['id']
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('failure', ['unsafe_id', 'schema', 'ambiguous_manifest', 'oversized', 'invalid_zip', 'duplicate_json'])
def test_archive_identifier_rejects_unsafe_or_ambiguous_metadata(dataset, monkeypatch, failure):
    manifest, files = dataset
    if failure == 'unsafe_id':
        manifest['id'] = '../outside'
    elif failure == 'schema':
        manifest['schema'] = 'unknown'
    extra = [('Manifest.json', json.dumps(manifest))] if failure == 'ambiguous_manifest' else []
    raw = '{"id":"a","id":"b"}' if failure == 'duplicate_json' else None
    data = archive(manifest, files, extra=extra, raw_manifest=raw)
    if failure == 'oversized':
        monkeypatch.setattr(corpus, 'MAX_MANIFEST_BYTES', 10)
    if failure == 'invalid_zip':
        data = b'not a ZIP archive'
    with pytest.raises(ValueError):
        imports.archive_identifier(data)

