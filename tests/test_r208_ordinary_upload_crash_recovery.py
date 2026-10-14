import json
import pytest
from app import ai_upload_transaction as tx

@pytest.fixture
def folder(tmp_path, monkeypatch):
    import app.storage as storage
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(tx, 'pdir', lambda _: tmp_path / 'project')
    p = tmp_path / 'project'
    (p/'audio').mkdir(parents=True)
    (p/'originals').mkdir()
    (p/'project.json').write_text('{}')
    return p

def test_uncommitted_crash_removes_only_new_files(folder, monkeypatch):
    monkeypatch.setattr(tx, 'load_project', lambda _: type('Project', (), {'tracks': [], 'clip_library': []})())
    (folder/'audio'/'existing.wav').write_bytes(b'old')
    (folder/'originals'/'existing.wav').write_bytes(b'old')
    tx.begin('project')
    (folder/'audio'/'new.wav').write_bytes(b'new')
    (folder/'originals'/'new.wav').write_bytes(b'new')
    assert tx.reconcile('project')['removed'] == 2
    assert (folder/'audio'/'existing.wav').read_bytes() == b'old'
    assert (folder/'originals'/'existing.wav').read_bytes() == b'old'
    assert not (folder/tx.NAME).exists()

def test_committed_track_keeps_audio_and_original(folder, monkeypatch):
    project = type('Project', (), {'tracks': [], 'clip_library': []})()
    monkeypatch.setattr(tx, 'load_project', lambda _: project)
    tx.begin('project')
    (folder/'audio'/'new.wav').write_bytes(b'new')
    (folder/'originals'/'new.wav').write_bytes(b'new')
    project.tracks.append(type('Track', (), {'filename': 'new.wav'})())
    assert tx.finish('project')['committed']
    assert (folder/'audio'/'new.wav').exists()
    assert (folder/'originals'/'new.wav').exists()

def test_damaged_journal_fails_closed(folder, monkeypatch):
    (folder/tx.NAME).write_text('{invalid')
    (folder/'audio'/'important.wav').write_bytes(b'data')
    with pytest.raises(json.JSONDecodeError): tx.reconcile('project')
    assert (folder/'audio'/'important.wav').exists()
    assert (folder/tx.NAME).exists()

def test_symlink_journal_fails_closed(folder):
    outside = folder.parent/'outside'
    outside.write_text('secret')
    (folder/tx.NAME).symlink_to(outside)
    with pytest.raises(RuntimeError): tx.reconcile('project')
    assert outside.read_text() == 'secret'

def test_begin_does_not_override_unresolved_journal(folder):
    (folder/tx.NAME).write_text('invalid')
    with pytest.raises(json.JSONDecodeError): tx.begin('project')
