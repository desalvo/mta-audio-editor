"""Fail-closed shared media and garbage collector end-to-end regressions."""
import hashlib


from types import SimpleNamespace
import pytest
from app import storage


def fixture_paths(monkeypatch, tmp_path):
    project_dir = tmp_path / 'projects' / 'abcdef123456'
    (project_dir / 'audio').mkdir(parents=True)
    shared = tmp_path / 'shared'
    monkeypatch.setattr(storage, 'ROOT', project_dir.parent)
    monkeypatch.setattr(storage, 'SHARED_MEDIA_ROOT', shared)
    monkeypatch.setattr(storage, 'SHARED_AUDIO_ROOT', shared / 'audio')
    monkeypatch.setattr(storage, 'SHARED_INDEX_PATH', shared / 'index.json')
    monkeypatch.setattr(storage, 'load_project', lambda pid: SimpleNamespace(tracks=[SimpleNamespace(filename='good.wav')], archived_tracks=[], clip_library=[]))
    (project_dir / 'project.json').write_text('{}')
    (project_dir / 'audio' / 'good.wav').write_bytes(b'valid media')
    return project_dir, shared


def test_01_rejects_shared_index_symlink(tmp_path, monkeypatch):
    p, shared = fixture_paths(monkeypatch, tmp_path)
    shared.mkdir()
    outside = tmp_path / 'outside'
    outside.write_text('{}')
    (shared / 'index.json').symlink_to(outside)
    with pytest.raises(ValueError, match='index'):
        storage._load_shared_index()
    assert outside.read_text() == '{}'


def test_02_rejects_shared_index_symlink_writer(tmp_path, monkeypatch):
    p, shared = fixture_paths(monkeypatch, tmp_path)
    shared.mkdir()
    outside = tmp_path / 'outside'
    outside.write_text('{}')
    (shared / 'index.json').symlink_to(outside)
    with pytest.raises(ValueError, match='index'):
        storage._write_shared_index({'version': 1, 'assets': {}})
    assert outside.read_text() == '{}'


def test_03_promote_skips_symlink_local_audio(tmp_path, monkeypatch):
    p, shared = fixture_paths(monkeypatch, tmp_path)
    outside = tmp_path / 'outside'
    outside.write_bytes(b'external')
    (p / 'audio' / 'good.wav').unlink()
    (p / 'audio' / 'good.wav').symlink_to(outside)
    assert storage.promote_project_audio_to_shared(p.name)['linked'] == 0
    assert outside.read_bytes() == b'external'


def test_04_promote_rejects_blob_symlink(tmp_path, monkeypatch):
    p, shared = fixture_paths(monkeypatch, tmp_path)
    digest = hashlib.sha256(b'valid media').hexdigest()
    blob = storage._shared_blob_path(digest, '.wav')
    blob.parent.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.write_bytes(b'external')
    blob.symlink_to(outside)
    with pytest.raises(ValueError, match='blob'):
        storage.promote_project_audio_to_shared(p.name)
    assert outside.read_bytes() == b'external'


def test_05_promote_rejects_corrupted_existing_blob(tmp_path, monkeypatch):
    p, shared = fixture_paths(monkeypatch, tmp_path)
    digest = hashlib.sha256(b'valid media').hexdigest()
    blob = storage._shared_blob_path(digest, '.wav')
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='digest'):
        storage.promote_project_audio_to_shared(p.name)
    assert (p / 'audio' / 'good.wav').read_bytes() == b'valid media'


def test_06_rescan_cannot_delete_when_project_invalid(tmp_path, monkeypatch):
    p, shared = fixture_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(storage, 'load_project', lambda pid: (_ for _ in ()).throw(ValueError('bad project')))
    orphan = shared / 'audio' / 'xx' / 'orphan.wav'
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b'keep')
    with pytest.raises(ValueError, match='incomplete'):
        storage.rescan_shared_media(delete_unreferenced=True)
    assert orphan.read_bytes() == b'keep'


def test_07_rescan_refuses_symlink_shared_audio_root(tmp_path, monkeypatch):
    p, shared = fixture_paths(monkeypatch, tmp_path)
    external = tmp_path / 'external'
    external.mkdir()
    shared.mkdir()
    (shared / 'audio').symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match='directory'):
        storage.rescan_shared_media(delete_unreferenced=True)


def test_08_rescan_skips_symlink_orphans(tmp_path, monkeypatch):
    p, shared = fixture_paths(monkeypatch, tmp_path)
    storage.promote_project_audio_to_shared(p.name)
    external = tmp_path / 'external'
    external.write_bytes(b'external')
    alias = shared / 'audio' / 'xx' / 'orphan.wav'
    alias.parent.mkdir(parents=True)
    alias.symlink_to(external)
    storage.rescan_shared_media(delete_unreferenced=True)
    assert alias.is_symlink() and external.read_bytes() == b'external'


def test_09_gc_worker_stops_on_failed_delete(tmp_path, monkeypatch):
    p, shared = fixture_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(storage, 'pdir', lambda pid: p)
    monkeypatch.setattr(storage.time, 'sleep', lambda s: None)
    storage._write_gc_queue(p.name, {'orphan.wav'})
    calls = []
    def stuck(pid):
        calls.append(pid)
        return {'deleted': 0, 'skipped': 1}
    monkeypatch.setattr(storage, 'run_project_gc', stuck)
    storage._GC_ACTIVE.add(p.name)
    storage._gc_worker(p.name)
    assert len(calls) == 1
    assert p.name not in storage._GC_ACTIVE
    assert storage._read_gc_queue(p.name) == {'orphan.wav'}


def test_10_startup_ignores_symlink_project(tmp_path, monkeypatch):
    p, shared = fixture_paths(monkeypatch, tmp_path)
    outside = tmp_path / 'outside'
    (outside / 'audio').mkdir(parents=True)
    (outside / 'project.json').write_text('{}')
    (p.parent / '123456abcdef').symlink_to(outside, target_is_directory=True)
    seen = []
    monkeypatch.setattr(storage, 'schedule_project_gc', lambda pid, **kw: seen.append(pid))
    storage.resume_pending_gc()
    assert seen == [p.name]
