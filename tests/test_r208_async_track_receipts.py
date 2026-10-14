import json
import pytest
from app import ai_async_track_transaction as tx

@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(tx, 'pdir', lambda _: tmp_path / 'project')
    p = tmp_path / 'project'
    (p / 'audio').mkdir(parents=True)
    (p / 'project.json').write_text('{}')
    return p


def test_async_uncommitted_files_cleaned(folder, monkeypatch):
    monkeypatch.setattr(tx, 'load_project', lambda _: type('P', (), {'tracks': [], 'clip_library': []})())
    tx.begin('project', 'a'*16, 'abc123def0.mp3')
    (folder/'audio'/'abc123def0.mp3').write_bytes(b'new')
    (folder/'audio'/'abc123def0-sr44100.wav').write_bytes(b'converted')
    (folder/'audio'/'unrelated.wav').write_bytes(b'other')
    assert tx.reconcile('project', 'a'*16)['removed'] == 2
    assert (folder/'audio'/'unrelated.wav').exists()


def test_async_committed_track_preserved(folder, monkeypatch):
    p = type('P', (), {'tracks': [type('T', (), {'filename': 'abc123def0-sr44100.wav'})()], 'clip_library': []})()
    monkeypatch.setattr(tx, 'load_project', lambda _: p)
    tx.begin('project', 'a'*16, 'abc123def0.mp3')
    (folder/'audio'/'abc123def0-sr44100.wav').write_bytes(b'committed')
    assert tx.reconcile('project', 'a'*16)['removed'] == 0
    assert (folder/'audio'/'abc123def0-sr44100.wav').exists()


def test_async_corrupt_receipt_preserved(folder):
    receipt = folder / (tx._PREFIX + 'a'*16 + tx._SUFFIX)
    receipt.write_text('{broken')
    with pytest.raises(json.JSONDecodeError):
        tx.reconcile('project', 'a'*16)
    assert receipt.exists()


def test_async_symlink_receipt_rejected(folder):
    outside = folder.parent / 'outside'
    outside.write_text('sensitive')
    (folder / (tx._PREFIX + 'a'*16 + tx._SUFFIX)).symlink_to(outside)
    with pytest.raises(RuntimeError):
        tx.reconcile('project', 'a'*16)
    assert outside.read_text() == 'sensitive'


def test_async_refuses_overwrite(folder):
    (folder/'audio'/'abc123def0.mp3').write_bytes(b'old')
    with pytest.raises(RuntimeError):
        tx.begin('project', 'a'*16, 'abc123def0.mp3')


def test_async_uncommitted_original_removed(folder, monkeypatch):
    monkeypatch.setattr(tx, 'load_project', lambda _: type('P', (), {'tracks': [], 'clip_library': []})())
    (folder/'originals').mkdir()
    from app import storage
    monkeypatch.setattr(storage, 'pdir', lambda _: folder)
    monkeypatch.setattr(storage, 'find_duplicate_project_file', lambda *_: None)
    tx.begin('project', 'b'*16, 'abc123def0.mp3')
    src = folder/'audio'/'abc123def0.mp3'
    src.write_bytes(b'source')
    original = tx.preserve_job_original('project', 'b'*16, src, 'music.mp3')
    assert original.exists()
    assert tx.reconcile('project', 'b'*16)['removed'] == 2
    assert not original.exists()


def test_async_committed_original_retained(folder, monkeypatch):
    monkeypatch.setattr(tx, 'load_project', lambda _: type('P', (), {'tracks': [type('T', (), {'filename': 'abc123def0.mp3'})()], 'clip_library': []})())
    (folder/'originals').mkdir()
    from app import storage
    monkeypatch.setattr(storage, 'pdir', lambda _: folder)
    monkeypatch.setattr(storage, 'find_duplicate_project_file', lambda *_: None)
    tx.begin('project', 'c'*16, 'abc123def0.mp3')
    src = folder/'audio'/'abc123def0.mp3'
    src.write_bytes(b'source')
    original = tx.preserve_job_original('project', 'c'*16, src, 'music.mp3')
    tx.reconcile('project', 'c'*16)
    assert original.read_bytes() == b'source'


def test_async_corrupt_original_path_fails_closed(folder, monkeypatch):
    monkeypatch.setattr(tx, 'load_project', lambda _: type('P', (), {'tracks': [], 'clip_library': []})())
    tx.begin('project', 'd'*16, 'abc123def0.mp3')
    receipt = tx._receipt('project', 'd'*16)
    obj = json.loads(receipt.read_text())
    obj.update(version=2, originals=['../bad'])
    receipt.write_text(json.dumps(obj))
    with pytest.raises(RuntimeError):
        tx.reconcile('project', 'd'*16)
    assert receipt.exists()
