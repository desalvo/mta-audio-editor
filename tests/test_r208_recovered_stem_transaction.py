
from types import SimpleNamespace
import pytest
from app import ai_recovered_stem_transaction as tx
from app.ai_media_identity import record


def sandbox(monkeypatch, tmp_path, receipts=()):
    folder = tmp_path / 'project'
    (folder / 'audio').mkdir(parents=True)
    (folder / 'originals').mkdir()
    monkeypatch.setattr(tx, 'pdir', lambda pid: folder)
    monkeypatch.setattr(tx, 'load_project', lambda pid: SimpleNamespace(
        recovered_ai_imports=list(receipts), tracks=[], clip_library=[]))
    return folder


def test_rollback_orphans_after_interruption(monkeypatch, tmp_path):
    root = sandbox(monkeypatch, tmp_path)
    (root / 'audio' / 'old.wav').write_bytes(b'old')
    tx.begin('proj', 'stems:demucs:id')
    (root / 'audio' / 'new.wav').write_bytes(b'new')
    (root / 'originals' / 'new-original.wav').write_bytes(b'new')
    record(root / tx._NAME, root / 'audio' / 'new.wav')
    record(root / tx._NAME, root / 'originals' / 'new-original.wav')
    result = tx.reconcile('proj')
    assert result['removed'] == 2 and result['committed'] is False
    assert (root / 'audio' / 'old.wav').exists()
    assert not (root / 'audio' / 'new.wav').exists()
    assert not (root / tx._NAME).exists()


def test_preserve_committed_stems(monkeypatch, tmp_path):
    receipt = 'stems:demucs:id'
    root = sandbox(monkeypatch, tmp_path, receipts=[receipt])
    tx.begin('proj', receipt)
    (root / 'audio' / 'new.wav').write_bytes(b'new')
    assert tx.reconcile('proj')['committed'] is True
    assert (root / 'audio' / 'new.wav').exists()


def test_preserve_other_referenced_files(monkeypatch, tmp_path):
    root = sandbox(monkeypatch, tmp_path)
    tx.begin('proj', 'stems:demucs:id')
    (root / 'audio' / 'referenced.wav').write_bytes(b'x')
    monkeypatch.setattr(tx, 'load_project', lambda pid: SimpleNamespace(
        recovered_ai_imports=[], tracks=[SimpleNamespace(filename='referenced.wav')], clip_library=[]))
    tx.reconcile('proj')
    assert (root / 'audio' / 'referenced.wav').exists()


def test_reject_corrupt_journal_without_deleting_audio(monkeypatch, tmp_path):
    root = sandbox(monkeypatch, tmp_path)
    (root / tx._NAME).write_text('{bad')
    (root / 'audio' / 'file.wav').write_bytes(b'file')
    with pytest.raises(ValueError):
        tx.reconcile('proj')
    assert (root / 'audio' / 'file.wav').exists()


def test_reject_second_begin_before_reconciliation(monkeypatch, tmp_path):
    sandbox(monkeypatch, tmp_path)
    tx.begin('proj', 'first')
    with pytest.raises(RuntimeError):
        tx.begin('proj', 'second')


def test_unowned_media_survives_recovery(monkeypatch, tmp_path):
    root = sandbox(monkeypatch, tmp_path)
    tx.begin('proj', 'stems:demucs:crash')
    (root / 'audio' / 'unrelated.wav').write_bytes(b'other upload')
    (root / 'originals' / 'unrelated-original.wav').write_bytes(b'other original')
    result = tx.reconcile('proj')
    assert result['removed'] == 0
    assert result['preserved_unowned'] == 2
    assert (root / 'audio' / 'unrelated.wav').read_bytes() == b'other upload'
    assert (root / 'originals' / 'unrelated-original.wav').read_bytes() == b'other original'


def test_replaced_owned_inode_survives_recovery(monkeypatch, tmp_path):
    root = sandbox(monkeypatch, tmp_path)
    tx.begin('proj', 'stems:demucs:crash')
    target = root / 'audio' / 'owned.wav'
    target.write_bytes(b'owned')
    record(root / tx._NAME, target)
    replacement = root / 'audio' / 'replacement.tmp'
    replacement.write_bytes(b'not ours')
    replacement.replace(target)
    result = tx.reconcile('proj')
    assert result['removed'] == 0
    assert result['preserved_replaced'] == 1
    assert target.read_bytes() == b'not ours'


def test_legacy_journal_remains_recoverable(monkeypatch, tmp_path):
    import json
    root = sandbox(monkeypatch, tmp_path)
    (root / tx._NAME).write_text(json.dumps({'version': 1, 'receipt': 'stems:old',
        'audio_before': [], 'originals_before': []}))
    (root / 'audio' / 'legacy-orphan.wav').write_bytes(b'old')
    assert tx.reconcile('proj')['removed'] == 1
