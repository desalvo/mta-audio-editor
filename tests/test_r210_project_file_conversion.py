"""Project media conversion preserves samples, references and recoverable backups."""
import shutil
import subprocess
from pathlib import Path

import pytest

from app import project_media_conversion as conversion, project_media_usage, storage
from app.models import Clip, ProjectClip, Track


@pytest.fixture
def media_project(tmp_path, monkeypatch):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('FFmpeg required')
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    empty = lambda pid: ({'audio':set(), 'original':set()}, False)
    monkeypatch.setattr(project_media_usage, 'pending_files', empty)
    monkeypatch.setattr(conversion, 'pending_files', empty)
    project = storage.create_project('Convert')
    audio = storage.audio_path(project.id, 'source.wav')
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=2',
                    '-ac','2','-c:a','pcm_s24le',str(audio)], check=True)
    project.tracks = [Track(id='t1',name='Drums',filename='source.wav',duration_ms=2000,
                            clips=[Clip(id='c', source_start_ms=250, source_end_ms=1750, timeline_start_ms=500)]),
                      Track(id='t2',name='Choir',filename='source.wav',duration_ms=2000)]
    project.clip_library = [ProjectClip(id='a', name='Source', filename='source.wav', current_location='audio/source.wav')]
    storage.save_project(project)
    return project


def test_convert_and_restore_shared_source_and_manual_backup_deletion(media_project):
    pid = media_project.id
    original = storage.audio_path(pid, 'source.wav')
    initial_hash = storage.file_sha256(original)
    before = storage.project_files(pid)
    row = next(item for item in before if item['name'] == 'source.wav')
    assert [item['name'] for item in row['tracks']] == ['Drums', 'Choir']
    result = conversion.convert(pid, 'source.wav', 'flac')
    assert result['tracks_updated'] == 2 and result['filename'].endswith('.flac')
    project = storage.load_project(pid)
    assert all(track.filename == result['filename'] for track in project.tracks)
    assert project.clip_library[0].filename == result['filename']
    assert project.tracks[0].clips[0].timeline_start_ms == 500
    backup = storage.original_path(pid, result['backup'])
    assert storage.file_sha256(backup) == initial_hash
    project_media_usage.cleanup(pid, remove_unused_library=True)
    assert backup.exists()
    entry = next(item for item in storage.project_files(pid) if item['name'] == backup.name)
    assert entry['backup_for'] == result['filename']
    restored = conversion.restore(pid, entry['backup_id'])
    assert storage.file_sha256(storage.audio_path(pid, restored['filename'])) == initial_hash
    assert all(track.filename == restored['filename'] for track in storage.load_project(pid).tracks)
    assert storage.original_path(pid, restored['backup']).exists()
    storage.delete_project_file(pid, 'original', entry['name'])
    assert not backup.exists() and all(item.filename != entry['name'] for item in storage.load_project(pid).media_backups)


def test_conversion_failure_leaves_source_and_project_unchanged(media_project, monkeypatch):
    pid = media_project.id
    monkeypatch.setattr(conversion, '_pcm_hash', lambda path: str(path))
    with pytest.raises(ValueError, match='verifica'):
        conversion.convert(pid, 'source.wav', 'flac')
    assert storage.audio_path(pid, 'source.wav').exists()
    project = storage.load_project(pid)
    assert [track.filename for track in project.tracks] == ['source.wav', 'source.wav']
    assert project.media_backups == []


def test_conversion_waits_for_pending_work(media_project, monkeypatch):
    monkeypatch.setattr(conversion, 'pending_files', lambda pid: ({'audio':set(), 'original':set()}, True))
    with pytest.raises(ValueError, match='job'):
        conversion.convert(media_project.id, 'source.wav', 'flac')
    assert storage.audio_path(media_project.id, 'source.wav').exists()


def test_lossless_flac_to_wav_keeps_previous_backup(media_project):
    pid = media_project.id
    flac = conversion.convert(pid, 'source.wav', 'flac')
    flac_hash = storage.file_sha256(storage.audio_path(pid, flac['filename']))
    wav = conversion.convert(pid, flac['filename'], 'wav')
    project = storage.load_project(pid)
    assert wav['filename'].endswith('.wav') and project.audio_storage_mode == 'wav'
    assert len(project.media_backups) == 2
    assert all(item.current_filename == wav['filename'] for item in project.media_backups)
    assert storage.file_sha256(storage.original_path(pid, wav['backup'])) == flac_hash


def test_quota_rejection_keeps_original_and_does_not_commit(media_project):
    def reject(_owner, _size):
        raise ValueError('quota')
    with pytest.raises(ValueError, match='quota'):
        conversion.convert(media_project.id, 'source.wav', 'flac', capacity_check=reject)
    project = storage.load_project(media_project.id)
    assert project.tracks[0].filename == 'source.wav' and not project.media_backups
    assert storage.audio_path(media_project.id, 'source.wav').exists()


def test_pending_backup_cannot_be_deleted(media_project, monkeypatch):
    result = conversion.convert(media_project.id, 'source.wav', 'flac')
    monkeypatch.setattr(project_media_usage, 'pending_files', lambda pid: ({'audio':set(), 'original':{result['backup']}}, True))
    with pytest.raises(ValueError, match='pending job'):
        storage.delete_project_file(media_project.id, 'original', result['backup'])
    assert storage.original_path(media_project.id, result['backup']).exists()


def test_symlink_source_is_rejected(media_project):
    pid = media_project.id
    alias = storage.pdir(pid) / 'audio' / 'alias.wav'
    alias.symlink_to('source.wav')
    project = storage.load_project(pid)
    project.tracks[0].filename = 'alias.wav'
    storage.save_project(project)
    with pytest.raises(ValueError, match='Collegamento'):
        conversion.convert(pid, 'alias.wav', 'flac')
    assert storage.audio_path(pid, 'source.wav').is_file()


def test_backup_can_be_reassigned_to_a_different_source(media_project):
    pid = media_project.id
    second = storage.audio_path(pid, 'other.wav')
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=880:duration=2',
                    '-c:a','pcm_s16le',str(second)], check=True)
    project = storage.load_project(pid)
    project.tracks.append(Track(id='t3', name='Other', filename='other.wav', duration_ms=2000))
    storage.save_project(project)
    converted = conversion.convert(pid, 'source.wav', 'flac')
    record = storage.load_project(pid).media_backups[0]
    restored = conversion.restore(pid, record.id, 'other.wav')
    tracks = {t.id:t.filename for t in storage.load_project(pid).tracks}
    assert tracks['t1'] == tracks['t2'] == converted['filename']
    assert tracks['t3'] == restored['filename']
    assert storage.file_sha256(storage.audio_path(pid, restored['filename'])) == storage.file_sha256(storage.original_path(pid, record.filename))


def test_project_files_ui_displays_track_and_backup_actions():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required')
    root = Path(__file__).resolve().parents[1]
    script = r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync('app/static/app.js','utf8');
const start=source.indexOf('async function manageProjectFiles(){'),end=source.indexOf('async function convertProjectMedia(',start);
assert.ok(start>=0&&end>start);let html='';
let current={id:'p'},files=[{category:'audio',name:'beat.wav',size:10,timeline:true,reusable:true,tracks:[{name:'Drums'}]},
{category:'original',name:'backup.wav',size:10,backup_id:'backup1',backup_for:'beat.wav',tracks:[]}];
async function api(){return files}function esc(x){return String(x)}function tr(en,it){return it}function toast(){}
function showUtilityModal(_title,value){html=value}function $(){return {addEventListener(){}}}function uploadExtraProjectFile(){}
eval(source.slice(start,end));
manageProjectFiles().then(()=>{assert.match(html,/<th>Tracce<\/th>/);assert.ok(html.includes('Drums'));assert.ok(html.includes('Converti FLAC'));assert.ok(html.includes('backupTarget-backup1'));assert.ok(html.includes('Ripristina'))}).catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run([node, '-e', script], cwd=root, check=True, capture_output=True, text=True, timeout=20)
