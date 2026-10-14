"""Sample editor publication rollback and durability regression."""
import contextlib
from pathlib import Path
import pytest

from app import sample_editor, storage
from app.models import Clip, Track


def _fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(sample_editor, 'media_duration_ms', lambda path: 500)
    monkeypatch.setattr(sample_editor, 'waveform_peaks', lambda path, count: [0.1])
    from app.ai_project_lock import project_publication_lock
    import app.ai_project_lock as locks
    monkeypatch.setattr(locks, 'project_publication_lock', lambda pid: contextlib.nullcontext())
    project = storage.create_project('atomic editor')
    track = Track(id='t1', name='Before', filename='before.wav', duration_ms=1000,
                  clips=[Clip(id='c1', source_start_ms=0, source_end_ms=1000, timeline_start_ms=100)])
    project.tracks = [track]
    storage.audio_path(project.id, 'before.wav').write_bytes(b'old')
    storage.save_project(project)
    tmp = storage.pdir(project.id) / '.render.wav'
    tmp.write_bytes(b'new valid bytes')
    return project, track, tmp


def test_commit_publishes_file_and_project(tmp_path, monkeypatch):
    p, track, tmp = _fixture(tmp_path, monkeypatch)
    sample_editor.commit(p, track, tmp)
    assert not tmp.exists()
    assert storage.audio_path(p.id, track.filename).read_bytes() == b'new valid bytes'
    assert storage.load_project(p.id).tracks[0].filename == track.filename
    assert storage.audio_path(p.id, 'before.wav').read_bytes() == b'old'
    assert not list((storage.pdir(p.id) / 'audio').glob('*.staged'))


def test_commit_failed_save_restores_track_and_discards_new_audio(tmp_path, monkeypatch):
    p, track, tmp = _fixture(tmp_path, monkeypatch)
    before = track.model_dump()
    def fail(*args, **kwargs):
        raise OSError('injected save failure')
    monkeypatch.setattr(storage, 'save_project', fail)
    with pytest.raises(OSError, match='injected'):
        sample_editor.commit(p, track, tmp)
    assert track.model_dump() == before
    assert storage.audio_path(p.id, 'before.wav').read_bytes() == b'old'
    assert sorted(x.name for x in (storage.pdir(p.id) / 'audio').iterdir()) == ['before.wav']
    assert not tmp.exists()


def test_analysis_failure_does_not_change_project(tmp_path, monkeypatch):
    p, track, tmp = _fixture(tmp_path, monkeypatch)
    before = track.model_dump()
    def fail(*args, **kwargs):
        raise RuntimeError('bad waveform')
    monkeypatch.setattr(sample_editor, 'waveform_peaks', fail)
    with pytest.raises(RuntimeError, match='bad waveform'):
        sample_editor.commit(p, track, tmp)
    assert track.model_dump() == before
    assert storage.load_project(p.id).tracks[0].filename == 'before.wav'
    assert sorted(x.name for x in (storage.pdir(p.id) / 'audio').iterdir()) == ['before.wav']


def test_symlink_render_is_rejected(tmp_path, monkeypatch):
    p, track, tmp = _fixture(tmp_path, monkeypatch)
    tmp.unlink()
    tmp.symlink_to(storage.audio_path(p.id, 'before.wav'))
    with pytest.raises(ValueError, match='unsafe'):
        sample_editor.commit(p, track, tmp)
    assert storage.audio_path(p.id, 'before.wav').read_bytes() == b'old'


def test_save_error_after_metadata_commit_preserves_referenced_audio(tmp_path, monkeypatch):
    p, track, tmp = _fixture(tmp_path, monkeypatch)
    real_save = storage.save_project
    def after_commit(*args, **kwargs):
        real_save(*args, **kwargs)
        raise OSError('post-commit fsync failure')
    monkeypatch.setattr(storage, 'save_project', after_commit)
    with pytest.raises(OSError, match='post-commit'):
        sample_editor.commit(p, track, tmp)
    persisted = storage.load_project(p.id).tracks[0]
    assert persisted.filename != 'before.wav'
    assert storage.audio_path(p.id, persisted.filename).read_bytes() == b'new valid bytes'
    assert not tmp.exists()
