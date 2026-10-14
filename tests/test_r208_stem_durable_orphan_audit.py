import json
from types import SimpleNamespace
import pytest
from app import ai_recovered_stem_transaction as tx
from app.ai_media_identity import record


def prepare(monkeypatch, tmp_path):
    project = tmp_path / 'proj'
    (project / 'audio').mkdir(parents=True)
    (project / 'originals').mkdir()
    monkeypatch.setattr(tx, 'pdir', lambda pid: project)
    monkeypatch.setattr(tx, 'load_project', lambda pid: SimpleNamespace(
        recovered_ai_imports=[], tracks=[], clip_library=[]))
    return project


def test_orphan_audit_survives_journal_retirement(monkeypatch, tmp_path):
    root = prepare(monkeypatch, tmp_path)
    tx.begin('proj', 'stems:worker:request')
    (root / 'audio' / 'foreign.wav').write_bytes(b'keep')
    assert tx.reconcile('proj')['preserved_unowned'] == 1
    assert not (root / tx._NAME).exists()
    report = json.loads((root / tx._ORPHANS).read_text())
    assert report == {'version': 1, 'items': [{'file': 'audio/foreign.wav',
        'reason': 'unowned', 'receipt': 'stems:worker:request'}]}
    assert (root / 'audio' / 'foreign.wav').read_bytes() == b'keep'


def test_audit_accumulates_across_recoveries(monkeypatch, tmp_path):
    root = prepare(monkeypatch, tmp_path)
    for receipt, name in [('first', 'first.wav'), ('second', 'second.wav')]:
        tx.begin('proj', receipt)
        (root / 'audio' / name).write_bytes(b'foreign')
        tx.reconcile('proj')
    report = json.loads((root / tx._ORPHANS).read_text())
    assert {(r['receipt'], r['file']) for r in report['items']} == {
        ('first', 'audio/first.wav'), ('second', 'audio/second.wav')}


def test_unsafe_audit_does_not_retire_journal_or_delete(monkeypatch, tmp_path):
    root = prepare(monkeypatch, tmp_path)
    tx.begin('proj', 'request')
    (root / 'audio' / 'keep.wav').write_bytes(b'keep')
    (root / tx._ORPHANS).symlink_to(root / 'audio' / 'keep.wav')
    with pytest.raises(RuntimeError, match='Unsafe'):
        tx.reconcile('proj')
    assert (root / tx._NAME).exists()
    assert (root / 'audio' / 'keep.wav').read_bytes() == b'keep'


def test_owned_cleanup_does_not_create_report(monkeypatch, tmp_path):
    root = prepare(monkeypatch, tmp_path)
    tx.begin('proj', 'request')
    artifact = root / 'audio' / 'owned.wav'
    artifact.write_bytes(b'owned')
    record(root / tx._NAME, artifact)
    assert tx.reconcile('proj')['removed'] == 1
    assert not (root / tx._ORPHANS).exists()
