
from app import storage
from app.models import Project, Track


def _mk_project(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    storage.ROOT.mkdir(parents=True, exist_ok=True)
    project = Project(id='abc123abc123', title='Preview GC')
    project.tracks = [Track(id='track-a', name='A', filename='a.wav', duration_ms=1000)]
    p = storage.pdir(project.id)
    (p / 'audio').mkdir(parents=True, exist_ok=True)
    (p / 'audio' / 'a.wav').write_bytes(b'a')
    storage.save_project(project)
    return project


def test_preview_gc_removes_deleted_track_and_keeps_recent(tmp_path, monkeypatch):
    project = _mk_project(tmp_path, monkeypatch)
    cache = storage.pdir(project.id) / '.preview'
    cache.mkdir()
    files = []
    for i in range(4):
        f = cache / f'track-a-sig{i}.wav'
        f.write_bytes(bytes([i]))
        f.touch()
        files.append(f)
    orphan = cache / 'deleted-track-old.wav'
    orphan.write_bytes(b'x')
    result = storage.cleanup_project_preview_cache(project.id, keep_per_track=2)
    assert result['preview_deleted'] == 3
    assert result['preview_kept'] == 2
    assert not orphan.exists()
    assert len(list(cache.glob('track-a-*.wav'))) == 2


def test_preview_gc_removes_master_preview(tmp_path, monkeypatch):
    project = _mk_project(tmp_path, monkeypatch)
    master = storage.pdir(project.id) / 'preview-master.mp3'
    master.write_bytes(b'mp3')
    result = storage.cleanup_project_preview_cache(project.id)
    assert result['preview_deleted'] == 1
    assert not master.exists()


def test_opening_maintenance_runs_preview_gc(tmp_path, monkeypatch):
    project = _mk_project(tmp_path, monkeypatch)
    cache = storage.pdir(project.id) / '.preview'
    cache.mkdir()
    (cache / 'removed-track-a.wav').write_bytes(b'x')
    monkeypatch.setattr(storage, 'promote_project_audio_to_shared', lambda pid: {'promoted': 0, 'linked': 0})
    result = storage.maintain_project_storage(project.id)
    assert result['preview_deleted'] >= 1
    assert not (cache / 'removed-track-a.wav').exists()
