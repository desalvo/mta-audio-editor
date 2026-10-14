"""Durable shared-media recovery must never prune uncertain references."""
import json
import pytest
from app import storage
from test_r208_ten_shared_gc_closures import fixture_paths


def test_corrupted_index_survives_rescan(tmp_path, monkeypatch):
    project, shared = fixture_paths(monkeypatch, tmp_path)
    shared.mkdir()
    index = shared / 'index.json'
    index.write_text('{invalid', encoding='utf-8')
    with pytest.raises(ValueError, match='index'):
        storage.rescan_shared_media()
    assert index.read_text() == '{invalid'


def test_unknown_schema_survives_rescan(tmp_path, monkeypatch):
    project, shared = fixture_paths(monkeypatch, tmp_path)
    shared.mkdir()
    index = shared / 'index.json'
    index.write_text(json.dumps({'version': 99, 'assets': {}}))
    with pytest.raises(ValueError, match='schema'):
        storage.rescan_shared_media(delete_unreferenced=True)
    assert json.loads(index.read_text())['version'] == 99


def test_missing_project_metadata_forbids_delete(tmp_path, monkeypatch):
    project, shared = fixture_paths(monkeypatch, tmp_path)
    (project / 'project.json').unlink()
    orphan = shared / 'audio' / 'aa' / 'orphan.wav'
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b'keep')
    with pytest.raises(ValueError, match='incomplete'):
        storage.rescan_shared_media(delete_unreferenced=True)
    assert orphan.read_bytes() == b'keep'


def test_symlink_project_metadata_forbids_delete(tmp_path, monkeypatch):
    project, shared = fixture_paths(monkeypatch, tmp_path)
    outside = tmp_path / 'external.json'
    outside.write_text('{}')
    (project / 'project.json').unlink()
    (project / 'project.json').symlink_to(outside)
    with pytest.raises(ValueError, match='incomplete'):
        storage.rescan_shared_media(delete_unreferenced=True)
    assert outside.read_text() == '{}'


def test_unknown_audio_reference_forbids_delete(tmp_path, monkeypatch):
    project, shared = fixture_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(storage, 'referenced_audio_files', lambda project: {'../bad.wav'})
    with pytest.raises(ValueError, match='incomplete'):
        storage.rescan_shared_media(delete_unreferenced=True)


def test_partial_rescan_does_not_overwrite_valid_index(tmp_path, monkeypatch):
    project, shared = fixture_paths(monkeypatch, tmp_path)
    shared.mkdir()
    index = shared / 'index.json'
    original = {'version': 1, 'assets': {'retained': {'refs': ['important']}}, 'updated_at': 7}
    index.write_text(json.dumps(original))
    (project / 'project.json').unlink()
    with pytest.raises(ValueError, match='incomplete'):
        storage.rescan_shared_media(delete_unreferenced=False)
    assert json.loads(index.read_text()) == original
