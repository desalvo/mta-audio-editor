"""End-to-end resilience for reusable clip instantiation (r208)."""
import shutil
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main, storage
from app.models import ProjectClip


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path.resolve())
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH', 'true')
    project = storage.create_project('Clip durability', 'DAW', sample_rate=48000)
    source = storage.audio_path(project.id, 'source.wav')
    with wave.open(str(source), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(44100)
        audio.writeframes(b'\x00\x00' * 1000)
    project.clip_library.append(ProjectClip(id='clip-a', name='Asset', filename='source.wav', duration_ms=23, sample_rate=44100))
    storage.save_project(project)
    client = TestClient(main.app, headers={'X-MTA-Request':'1'})
    return project, source, client


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg required')
def test_clip_conversion_persists_only_referenced_audio(tmp_path, monkeypatch):
    project, source, client = _setup(tmp_path, monkeypatch)
    response = client.post(f'/api/projects/{project.id}/clip-library/clip-a/instantiate', json={})
    assert response.status_code == 200, response.text
    saved = storage.load_project(project.id)
    assert len(saved.tracks) == 1
    assert saved.tracks[0].source_clip_id == 'clip-a'
    assert source.is_file()
    assert storage.audio_path(project.id, saved.tracks[0].filename).is_file()
    assert set(x.name for x in source.parent.iterdir()) == {'source.wav', saved.tracks[0].filename}


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg required')
def test_clip_conversion_save_failure_rolls_back_own_audio(tmp_path, monkeypatch):
    project, source, client = _setup(tmp_path, monkeypatch)
    def fail_save(*args, **kwargs):
        raise OSError('injected pre-commit failure')
    monkeypatch.setattr(main, 'save_project', fail_save)
    with pytest.raises(OSError, match='pre-commit'):
        client.post(f'/api/projects/{project.id}/clip-library/clip-a/instantiate', json={})
    assert source.is_file()
    assert set(x.name for x in source.parent.iterdir()) == {'source.wav'}
    assert storage.load_project(project.id).tracks == []


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg required')
def test_clip_post_commit_failure_keeps_referenced_audio(tmp_path, monkeypatch):
    project, source, client = _setup(tmp_path, monkeypatch)
    real_save = storage.save_project
    def post_commit_error(obj):
        real_save(obj)
        raise OSError('injected post-commit failure')
    monkeypatch.setattr(main, 'save_project', post_commit_error)
    with pytest.raises(OSError, match='post-commit'):
        client.post(f'/api/projects/{project.id}/clip-library/clip-a/instantiate', json={})
    persisted = storage.load_project(project.id)
    assert len(persisted.tracks) == 1
    assert storage.audio_path(project.id, persisted.tracks[0].filename).is_file()
    assert source.is_file()


def test_clip_symlink_source_rejected(tmp_path, monkeypatch):
    project, source, client = _setup(tmp_path, monkeypatch)
    source.unlink()
    external = tmp_path / 'external.wav'
    external.write_bytes(b'private')
    source.symlink_to(external)
    response = client.post(f'/api/projects/{project.id}/clip-library/clip-a/instantiate', json={})
    assert response.status_code in (400, 404), response.text
    assert external.read_bytes() == b'private'
