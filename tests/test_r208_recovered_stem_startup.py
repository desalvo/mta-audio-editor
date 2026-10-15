
from types import SimpleNamespace
from app import ai_recovered_stem_transaction as tx
from app import storage
from app.ai_media_identity import record


def test_startup_reconciles_uncommitted_and_preserves_completed(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(tx, 'pdir', lambda pid: tmp_path / pid)
    receipts = {}
    monkeypatch.setattr(tx, 'load_project', lambda pid: SimpleNamespace(
        recovered_ai_imports=receipts.get(pid, []), tracks=[], clip_library=[]))
    class FakeLock:
        def __init__(self, pid): self.pid = pid
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr('app.ai_project_lock.project_publication_lock', FakeLock)
    for pid in ('a' * 12, 'b' * 12):
        root = tmp_path / pid
        (root / 'audio').mkdir(parents=True)
        (root / 'originals').mkdir()
        (root / 'project.json').write_text('{}')
        tx.begin(pid, 'receipt')
        (root / 'audio' / 'new.wav').write_bytes(b'new')
        record(root / tx._NAME, root / 'audio' / 'new.wav')
    receipts['b' * 12] = ['receipt']
    stats = tx.reconcile_on_startup()
    assert stats == {'checked': 2, 'recovered': 2, 'removed': 1, 'preserved_unowned': 0, 'preserved_replaced': 0, 'errors': {}}
    assert not (tmp_path / ('a' * 12) / 'audio' / 'new.wav').exists()
    assert (tmp_path / ('b' * 12) / 'audio' / 'new.wav').exists()
    assert tx.reconcile_on_startup()['checked'] == 0


def test_startup_corrupt_journal_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setattr(tx, 'pdir', lambda pid: tmp_path / pid)
    class FakeLock:
        def __init__(self, pid): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
    monkeypatch.setattr('app.ai_project_lock.project_publication_lock', FakeLock)
    root = tmp_path / ('c' * 12)
    (root / 'audio').mkdir(parents=True)
    (root / 'project.json').write_text('{}')
    (root / tx._NAME).write_text('{bad')
    (root / 'audio' / 'valuable.wav').write_bytes(b'value')
    stats = tx.reconcile_on_startup()
    assert 'c' * 12 in stats['errors']
    assert (root / 'audio' / 'valuable.wav').read_bytes() == b'value'
    assert (root / tx._NAME).exists()
