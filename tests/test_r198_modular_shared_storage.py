from pathlib import Path

from app.models import Project, Track
from app import storage


def _project(pid: str, filename: str) -> Project:
    return Project(id=pid, title='Shared', tracks=[Track(id='t1', name='Audio', filename=filename, duration_ms=1000)])


def test_open_maintenance_removes_orphan_and_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    monkeypatch.setattr(storage, 'SHARED_MEDIA_ROOT', tmp_path / 'shared-media')
    monkeypatch.setattr(storage, 'SHARED_AUDIO_ROOT', tmp_path / 'shared-media' / 'audio')
    monkeypatch.setattr(storage, 'SHARED_INDEX_PATH', tmp_path / 'shared-media' / 'index.json')
    storage.ROOT.mkdir(parents=True)
    pid='aaaaaaaaaaaa'; base=storage.pdir(pid); (base/'audio').mkdir(parents=True)
    keep=base/'audio'/'keep.wav'; keep.write_bytes(b'RIFF-common-audio')
    orphan=base/'audio'/'old.wav'; orphan.write_bytes(b'old')
    storage.save_project(_project(pid, 'keep.wav'))
    result=storage.maintain_project_storage(pid)
    assert not orphan.exists()
    assert keep.exists()
    assert result['deleted'] == 1
    assert result['linked'] == 1
    assert storage.SHARED_INDEX_PATH.exists()


def test_shared_rescan_never_deletes_blob_referenced_by_any_project(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    monkeypatch.setattr(storage, 'SHARED_MEDIA_ROOT', tmp_path / 'shared-media')
    monkeypatch.setattr(storage, 'SHARED_AUDIO_ROOT', tmp_path / 'shared-media' / 'audio')
    monkeypatch.setattr(storage, 'SHARED_INDEX_PATH', tmp_path / 'shared-media' / 'index.json')
    storage.ROOT.mkdir(parents=True)
    for pid in ('aaaaaaaaaaaa','bbbbbbbbbbbb'):
        base=storage.pdir(pid); (base/'audio').mkdir(parents=True)
        (base/'audio'/'common.wav').write_bytes(b'same-content')
        storage.save_project(_project(pid, 'common.wav'))
    first=storage.rescan_shared_media(delete_unreferenced=True)
    assert first['assets'] == 1 and first['references'] == 2
    blob=next(storage.SHARED_AUDIO_ROOT.rglob('*.wav'))
    assert blob.exists()
    # Drop one project: the shared blob must survive because the second still references it.
    storage.delete_project('aaaaaaaaaaaa')
    second=storage.rescan_shared_media(delete_unreferenced=True)
    assert second['assets'] == 1
    assert blob.exists()


def test_native_autosave_no_longer_rewrites_maeproj():
    js=Path('app/static/app.js').read_text()
    start=js.index('async function persistCurrentProject')
    block=js[start:js.index('\n', start)+800]
    assert 'syncNativeProjectFile' not in block
    save_start=js.index('async function save(){')
    assert 'syncNativeProjectFile(current.id)' in js[save_start:save_start+800]


def test_revision_metadata_alignment():
    revision = int(Path('REVISION').read_text().strip())
    build_number = 30000 + revision
    android = Path('mobile/android/app/build.gradle.kts').read_text()
    ios = Path('mobile/ios/MTAEditorMobile/Info.plist').read_text()
    assert f'versionCode = {build_number}' in android
    assert f'buildConfigField("String", "MTA_REVISION", "\\"{revision}\\"")' in android
    assert f'<string>{build_number}</string>' in ios
    assert f'<key>MTAEditorRevision</key><string>{revision}</string>' in ios
