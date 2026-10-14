"""FLAC publication must not corrupt live references on failed project commit."""
import shutil
import subprocess
import pytest

from app.models import Track
from app import storage


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='ffmpeg required')
def test_flac_save_failure_restores_in_memory_references_and_queues_staged_files(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', (tmp_path / 'projects').resolve())
    project = storage.create_project('Crash safe WAV')
    audio = storage.audio_path(project.id, 'original.wav')
    subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=300:duration=0.2', '-c:a', 'pcm_s16le', str(audio)], check=True)
    project.tracks = [Track(id='track1', name='Audio', filename=audio.name, duration_ms=200)]
    storage.save_project(project)
    original_save = storage.save_project

    def fail_commit(*args, **kwargs):
        if kwargs.get('_skip_flac_conversion'):
            raise OSError('simulated commit failure')
        return original_save(*args, **kwargs)

    monkeypatch.setattr(storage, 'save_project', fail_commit)
    with pytest.raises(OSError, match='simulated commit failure'):
        storage.migrate_project_audio_to_flac(project)
    assert project.tracks[0].filename == 'original.wav'
    assert project.audio_storage_mode == 'wav'
    assert storage.load_project(project.id).tracks[0].filename == 'original.wav'
    assert audio.is_file()
    queued = storage._read_gc_queue(project.id)
    assert any(x.endswith('.flac') for x in queued)
    storage.run_project_gc(project.id)
    assert audio.is_file()
    assert not any(x.endswith('.flac') for x in storage._read_gc_queue(project.id))
