"""FLAC storage must never leak into MTA, and must preserve clip time."""
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from app.models import Clip, Track, Marker


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='ffmpeg required')
def test_flac_migration_and_mta_export_preserve_timeline(tmp_path, monkeypatch):
    import app.storage as storage
    from app.codec import export_mta, ffprobe
    from app.mta_reverse import deobfuscate_media_copy
    monkeypatch.setattr(storage, 'ROOT', (tmp_path / 'workspace').resolve())
    project = storage.create_project('FLAC integration', target='MTA8', owner_user_id=1)
    source = storage.audio_path(project.id, 'beat.wav')
    subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','sine=frequency=880:duration=2',
                    '-ar','44100','-ac','2','-c:a','pcm_s24le',str(source)], check=True)
    project.tracks = [Track(id='drums1', name='Drums', filename='beat.wav', duration_ms=3000,
                           clips=[Clip(id='intro',source_start_ms=250,source_end_ms=1750,timeline_start_ms=850)])]
    project.markers = [Marker(time_ms=1000, label='Hit')]
    storage.save_project(project)
    result = storage.migrate_project_audio_to_flac(project)
    assert result['converted'] == 1
    assert project.audio_storage_mode == 'flac'
    assert project.tracks[0].filename.endswith('.flac')
    assert not source.exists()
    assert project.tracks[0].clips[0].timeline_start_ms == 850
    assert project.markers[0].time_ms == 1000
    new_source = storage.audio_path(project.id,project.tracks[0].filename)
    assert new_source.is_file()
    archive = tmp_path / 'portable.maeprojz'
    storage.write_project_archive(project.id, archive)
    with zipfile.ZipFile(archive) as z:
        assert f'project/audio/{new_source.name}' in z.namelist()
        assert 'project/audio/beat.wav' not in z.namelist()
        assert json.loads(z.read('project/project.json'))['audio_storage_mode'] == 'flac'
    output = tmp_path / 'from-flac.mta'
    export_mta(project, output)
    normalized = tmp_path / 'audio.mka'
    deobfuscate_media_copy(output, normalized)
    streams=[x for x in ffprobe(normalized)['streams'] if x.get('codec_type') == 'audio']
    assert streams and all(x['codec_name'] == 'mp3' for x in streams)
    # MTA export must not encode FLAC; project has not lost marker/clip timing.
    assert storage.load_project(project.id).markers[0].time_ms == 1000
    assert storage.load_project(project.id).tracks[0].clips[0].timeline_start_ms == 850


def test_legacy_project_default_is_wav():
    from app.models import Project
    assert Project(id='abc123',title='Old').audio_storage_mode == 'wav'

@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='ffmpeg required')
def test_new_flac_project_converts_new_pcm_media_at_save(tmp_path, monkeypatch):
    import app.storage as storage
    monkeypatch.setattr(storage,'ROOT',(tmp_path/'projects').resolve())
    p=storage.create_project('New FLAC',audio_storage_mode='flac')
    src=storage.audio_path(p.id,'new.wav')
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','sine=frequency=120:duration=1',
                    '-c:a','pcm_s16le',str(src)],check=True)
    p.tracks=[Track(id='t1',name='Test',filename='new.wav',duration_ms=1000)]
    storage.save_project(p)
    assert p.tracks[0].filename.endswith('.flac')
    assert storage.audio_path(p.id,p.tracks[0].filename).exists()
    assert not src.exists()
    assert storage.load_project(p.id).audio_storage_mode=='flac'

@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='ffmpeg required')
def test_wav_project_does_not_convert_automatically(tmp_path, monkeypatch):
    import app.storage as storage
    monkeypatch.setattr(storage,'ROOT',(tmp_path/'projects').resolve())
    p=storage.create_project('Legacy WAV')
    src=storage.audio_path(p.id,'legacy.wav')
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','sine=frequency=120:duration=1',
                    '-c:a','pcm_s16le',str(src)],check=True)
    p.tracks=[Track(id='t1',name='Test',filename='legacy.wav',duration_ms=1000)]
    storage.save_project(p)
    assert p.tracks[0].filename=='legacy.wav'
    assert src.exists()
